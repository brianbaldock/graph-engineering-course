"""Keep the collaboration disclaimer's numbers true.

Lesson 0's "Who wrote this" section states how long Brian and Hermes have
worked together and
how much material came out of it. Those are factual claims on a site whose
opening argument is that unsourced numbers are decoration. So recompute
them from the real Hermes home and fail if the published figures drift.

The first draft of that note said "six months." The record said three.
This check is why that got caught before it shipped.
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

HERMES = Path.home() / ".hermes"
ROOT = Path(__file__).resolve().parent.parent
NOTE = ROOT / "src/components/CollabNote.astro"
LESSON0 = ROOT / "src/content/lessons/00-what-this-is.md"
STAMP = ROOT / "src/data/collab_stats.json"

# CollabNote.astro was removed (it repeated on every lesson). Lesson 0 is now
# the single disclosure. Read the component only if it comes back, so this
# script keeps working either way rather than crashing on a missing path.
text = NOTE.read_text() if NOTE.exists() else ""
lesson0 = LESSON0.read_text() if LESSON0.exists() else ""
if not lesson0:
    sys.exit("FAIL: 00-what-this-is.md is missing; cannot verify collaboration claims.")
# The counts are checked wherever they are actually asserted.
text = text + "\n" + lesson0

# Where the ground truth comes from.
#
# On the authoring machine we measure the real Hermes home. On a CI runner
# that directory does not exist, and an earlier version of this script simply
# printed SKIP and exited 0 there, which meant the check never actually ran
# where it mattered. So the authoring machine writes a signed-off snapshot to
# src/data/collab_stats.json, and CI validates the prose against that file.
# No measurable source and no snapshot is a hard failure, not a skip.
if HERMES.is_dir() and (HERMES / "journal").is_dir():
    journal = sorted(p.stem for p in (HERMES / "journal").glob("2*.md"))
    if not journal:
        sys.exit("FAIL: Hermes journal is empty; cannot verify collaboration claims.")
    first = date.fromisoformat(journal[0])
    last = date.fromisoformat(journal[-1])
    journal_days = len(journal)
    skills = len(list((HERMES / "skills").rglob("SKILL.md")))
    source = f"measured from {HERMES}"
    # Refresh the snapshot so CI has something authoritative to check.
    STAMP.parent.mkdir(parents=True, exist_ok=True)
    STAMP.write_text(json.dumps({
        "first_entry": journal[0],
        "last_entry": journal[-1],
        "journal_days": journal_days,
        "skills": skills,
    }, indent=2) + "\n")
elif STAMP.exists():
    snap = json.loads(STAMP.read_text())
    first = date.fromisoformat(snap["first_entry"])
    last = date.fromisoformat(snap["last_entry"])
    journal_days = snap["journal_days"]
    skills = snap["skills"]
    source = f"snapshot {STAMP.name}"
else:
    sys.exit(
        "FAIL: no Hermes home and no src/data/collab_stats.json snapshot.\n"
        "Cannot verify the collaboration claims, so this check fails rather "
        "than passing silently."
    )

months = (last - first).days / 30.44
weeks = (last - first).days / 7
print(f"{source}: {months:.1f} months, {journal_days} journal days, {skills} skills")

fails = []

# --- claimed duration ------------------------------------------------
# Accept either "roughly N months" or "about N weeks", whichever the note
# uses. Weeks are the honest unit while the span is under three months.
weeks = (last - first).days / 7
WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
         "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
         "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
         "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20}


def _num(word):
    return WORDS.get(word.lower(), int(word) if word.isdigit() else None)


def check_duration(blob, label):
    """Any duration claim about the collaboration, wherever it is written.

    Checked in BOTH directions. An earlier version only failed when the prose
    rounded UP, which meant "about one week" sailed through against a
    twelve-week record: technically not an overclaim, but still false, and a
    course about verifying numbers does not get to publish a false one just
    because it errs modestly. The band is deliberately generous on the low
    side because "about eleven weeks" against 11.6 real weeks is honest
    rounding, not drift.
    """
    found = False
    for pat, unit, limit in (
        (r"roughly (\w+) months", "months", months),
        (r"about (\w+) months", "months", months),
        (r"roughly (\w+) weeks", "weeks", weeks),
        (r"about (\w+) weeks", "weeks", weeks),
        (r"over (\w+) months", "months", months),
        (r"(\w+) months of", "months", months),
    ):
        for word in re.findall(pat, blob):
            claimed = _num(word)
            if claimed is None:
                continue
            found = True
            if claimed > limit:
                fails.append(
                    f"{label}: claims '{word} {unit}' but the record spans "
                    f"{limit:.1f} {unit}. Do not round up."
                )
            elif claimed < limit * 0.6:
                fails.append(
                    f"{label}: claims '{word} {unit}' but the record spans "
                    f"{limit:.1f} {unit}. That understates it enough to be wrong."
                )
    return found


found_note = check_duration(lesson0, "00-what-this-is.md")
if not found_note:
    fails.append("00-what-this-is.md: no duration claim found to verify")

# --- claimed counts --------------------------------------------------
# These lived in CollabNote.astro, a per-lesson banner that was removed as
# repetitive; Lesson 0's "Who wrote this" section is now the single place the
# collaboration is disclosed. The count patterns below are checked only if
# the prose still makes those claims. A claim that is not made cannot drift,
# but a claim that IS made still has to be true, so this stays fail-closed on
# a wrong number while tolerating a removed sentence.
for pattern, actual, label in (
    (r"(\d+) days of working notes", journal_days, "journal days"),
    (r"(\d+) skills", skills, "skills"),
):
    m = re.search(pattern, text)
    if not m:
        continue
    claimed = int(m.group(1))
    if claimed > actual:
        fails.append(f"claims {claimed} {label}, actual is {actual}. Do not round up.")

if fails:
    print("\nCOLLABORATION CLAIMS OUT OF DATE:")
    for f in fails:
        print(f"  {f}")
    print("\nUpdate the 'Who wrote this' section of "
          "src/content/lessons/00-what-this-is.md to match the measured values.")
    sys.exit(1)

print("Collaboration claims are backed by the record.")
