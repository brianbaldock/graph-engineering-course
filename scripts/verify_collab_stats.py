"""Keep the collaboration disclaimer's numbers true.

CollabNote.astro states how long Brian and Hermes have worked together and
how much material came out of it. Those are factual claims on a site whose
opening argument is that unsourced numbers are decoration. So recompute
them from the real Hermes home and fail if the published figures drift.

The first draft of that note said "six months." The record said three.
This check is why that got caught before it shipped.
"""
import re
import sys
from datetime import date
from pathlib import Path

HERMES = Path.home() / ".hermes"
NOTE = Path(__file__).resolve().parent.parent / "src/components/CollabNote.astro"

if not HERMES.is_dir():
    print(f"SKIP: no Hermes home at {HERMES} (not the authoring machine)")
    sys.exit(0)

text = NOTE.read_text()

# --- measure reality -------------------------------------------------
journal = sorted(p.stem for p in (HERMES / "journal").glob("2*.md"))
if not journal:
    print("SKIP: no journal entries to measure against")
    sys.exit(0)

first = date.fromisoformat(journal[0])
last = date.fromisoformat(journal[-1])
months = (last - first).days / 30.44
journal_days = len(journal)
skills = len(list((HERMES / "skills").rglob("SKILL.md")))

print(f"measured: {months:.1f} months, {journal_days} journal days, {skills} skills")

fails = []

# --- claimed duration ------------------------------------------------
# Accept either "roughly N months" or "about N weeks", whichever the note
# uses. Weeks are the honest unit while the span is under three months.
weeks = (last - first).days / 7
m_months = re.search(r"roughly (\w+) months", text)
m_weeks = re.search(r"about (\w+) weeks", text)
WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
         "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
         "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
         "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20}


def _num(word):
    return WORDS.get(word.lower(), int(word) if word.isdigit() else None)


if m_months:
    claimed = _num(m_months.group(1))
    if claimed is None:
        fails.append(f"unparseable duration word: {m_months.group(1)!r}")
    elif claimed > months:
        fails.append(
            f"claims 'roughly {m_months.group(1)} months' but the journal spans "
            f"{months:.1f}. Do not round up."
        )
elif m_weeks:
    claimed = _num(m_weeks.group(1))
    if claimed is None:
        fails.append(f"unparseable duration word: {m_weeks.group(1)!r}")
    elif claimed > weeks:
        fails.append(
            f"claims 'about {m_weeks.group(1)} weeks' but the journal spans "
            f"{weeks:.1f}. Do not round up."
        )
else:
    fails.append("no duration claim ('roughly N months' / 'about N weeks') found")

# --- claimed counts --------------------------------------------------
for pattern, actual, label in (
    (r"(\d+) days of working notes", journal_days, "journal days"),
    (r"(\d+) skills", skills, "skills"),
):
    m = re.search(pattern, text)
    if not m:
        fails.append(f"no {label} claim found")
        continue
    claimed = int(m.group(1))
    if claimed > actual:
        fails.append(f"claims {claimed} {label}, actual is {actual}. Do not round up.")

if fails:
    print("\nCOLLABORATION CLAIMS OUT OF DATE:")
    for f in fails:
        print(f"  {f}")
    print("\nUpdate src/components/CollabNote.astro to match the measured values.")
    sys.exit(1)

print("Collaboration claims are backed by the record.")
