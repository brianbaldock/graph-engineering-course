#!/usr/bin/env python3
"""Verify that lesson prose does not claim behaviour the code lacks.

Written after a specific failure. In one session I added a sentence to
Lesson 3 saying confidence is "a float the extractor sets and the
validation gate in Lesson 6 thresholds on." Every clause was false:
validate.py and extract.py never mention confidence, a 0.01 edge passes
the gate, and commit stores 1.0 regardless. I wrote it from a plausible
reading of the dataclass instead of from the code, and no gate caught it
because prose was the one artifact nothing checked.

The other gates verify commands, counts, links, and outputs. This one
verifies CLAIMS: each entry pairs a phrase that must not appear in the
lessons with a predicate proving the code does not support it. When a
reader wires confidence into the gate for real, the predicate flips and
the claim becomes publishable.

This cannot check all prose. It pins the specific claims that have
already been wrong once, which is the class most likely to regress.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LESSONS = ROOT / "src/content/lessons"
LABS = ROOT / "labs"
sys.path.insert(0, str(LABS))


def code_reads_confidence() -> bool:
    """True if any lab module actually reads the confidence field."""
    for mod in ("validate.py", "extract.py"):
        text = (LABS / "graphlab" / mod).read_text()
        # Strip comments and docstrings crudely: we want executable mentions.
        stripped = re.sub(r"#.*", "", text)
        stripped = re.sub(r'""".*?"""', "", stripped, flags=re.S)
        if "confidence" in stripped:
            return True
    return False


def code_uses_jsonschema() -> bool:
    text = (LABS / "graphlab/validate.py").read_text()
    return bool(re.search(r"^\s*(import|from)\s+jsonschema", text, re.M))


def pipeline_owns_close_logic() -> bool:
    """True if the close marker is produced/applied in pipeline.py itself."""
    text = (LABS / "graphlab/pipeline.py").read_text()
    return "_close" in text


# (claim regex, human description, predicate that must be TRUE to allow it)
#
# Match STRUCTURALLY, not by enumerating phrasings. The first version of this
# gate listed the exact sentence that had already been wrong once, so dropping
# three words from it walked straight through: a sabotage probe found only 2 of
# 8 natural phrasings caught. The list of guessed phrasings WAS the bug.
#
# But structure alone over-fires. A first structural draft flagged six lines of
# legitimate prose, including the Lesson 6 exercise that explicitly says nothing
# reads confidence and the Lesson 7 "enforced versus documented" disclaimer.
# Flagging the sentence that CORRECTS the misconception is the classic trap.
#
# So: assert an ACTIVE claim (the gate does threshold on confidence, in the
# present indicative, close together), then exclude hypotheticals ("a gate can
# enforce ... a confidence threshold"), exercise framing ("add a confidence
# floor"), demonstration output, and explicit disclaimers.
_ACTOR = r"(?:gate|validat\w+|extractor|commit\b|store\b|persist\w*)"
_ENFORCE = (r"(?:thresholds?\s+on|thresholds?\b|enforc\w+|rejects?\w*|filters?\w*"
            r"|discard\w*|drops?\b|prunes?\b|checks?\b|stricter|cutoff|floor"
            r"|never\s+reach\w*|does\s+not\s+reach)")

# Proximity model: the line mentions confidence, AND an actor, AND an enforcement
# verb, all within a bounded window of the word "confidence". Word order varies
# too much in natural prose to enumerate, but co-occurrence in a tight window is
# a reliable signal, and the window is what keeps unrelated uses of "confidence"
# (Lesson 2's "act on with full confidence") from matching.
_W = 80
_CLAIM_CONFIDENCE = (
    rf"confidence.{{0,{_W}}}{_ACTOR}"
    rf"|{_ACTOR}.{{0,{_W}}}confidence"
)
# Second condition applied in code below: an enforcement verb must also appear
# within the window. Encoded as a companion regex so both must hold.
_CONFIDENCE_ENFORCE_NEAR = re.compile(
    rf"confidence.{{0,{_W}}}{_ENFORCE}|{_ENFORCE}.{{0,{_W}}}confidence", re.I
)

# Narrow carve-outs. Each one exists because a real line of honest prose tripped
# the detector. Keep this list specific; an over-broad exclusion disarms the gate.
_DISCLAIM = re.compile(
    # explicit statements that it is NOT wired
    r"not (?:enforced|read|used|checked)|never (?:reads?|enforced|used|checked)"
    r"|nothing reads it|do not mention|enforces nothing"
    r"|looks like a (?:safety )?control|does not (?:read|enforce|gate|threshold)"
    r"|stores the default|the value you (?:passed|supplied) is not"
    # hypothetical / capability framing, not a claim about this lab
    r"|\bcan enforce\b|\bcould\b|\bwould\b|\bmay\b|\bshould\b"
    # exercise framing: telling the reader to BUILD it
    r"|\*\*Add a|Add a confidence|this exercise|you need four things"
    # demonstration output showing non-enforcement
    r"|accepted_edges=|passes the gate",
    re.I,
)

CLAIMS = [
    (
        _CLAIM_CONFIDENCE,
        "prose says confidence is enforced by the gate",
        code_reads_confidence,
        _CONFIDENCE_ENFORCE_NEAR,
    ),
    (
        r"(uses|via|with|through) (a )?JSON Schema (library|dependency|package)"
        r"|validated (against|with) (a )?JSON Schema",
        "prose implies a real JSON Schema dependency",
        code_uses_jsonschema,
        None,
    ),
    (
        r"`?pipeline\.py`? only handles this when",
        "prose attributes close-marker logic to pipeline.py",
        pipeline_owns_close_logic,
        None,
    ),
]

fails = []
for pattern, description, predicate, also_required in CLAIMS:
    supported = predicate()
    rx = re.compile(pattern, re.I)
    for lesson in sorted(LESSONS.glob("*.md")):
        for n, line in enumerate(lesson.read_text().splitlines(), 1):
            if not rx.search(line) or supported:
                continue
            if also_required is not None and not also_required.search(line):
                continue
            if _DISCLAIM.search(line):
                continue
            fails.append(
                f"{lesson.name}:{n}: {description}, but the code does not.\n"
                f"    {line.strip()[:110]}"
            )

if fails:
    print("UNSUPPORTED CLAIMS IN LESSON PROSE:")
    for f in fails:
        print(f"  {f}")
    print(
        "\nEither change the prose or wire the behaviour. A field that looks "
        "like a control but enforces nothing is the failure this course names."
    )
    sys.exit(1)

print(f"Checked {len(CLAIMS)} pinned claims against the code. All consistent.")
