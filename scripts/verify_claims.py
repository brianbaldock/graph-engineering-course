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
CLAIMS = [
    (
        r"gate in Lesson 6 thresholds on|gate thresholds on .{0,20}confidence"
        r"|confidence.{0,40}(is enforced|gates|rejects)",
        "prose says confidence is enforced by the gate",
        code_reads_confidence,
    ),
    (
        r"(uses|via|with|through) (a )?JSON Schema (library|dependency|package)"
        r"|validated (against|with) (a )?JSON Schema",
        "prose implies a real JSON Schema dependency",
        code_uses_jsonschema,
    ),
    (
        r"`?pipeline\.py`? only handles this when",
        "prose attributes close-marker logic to pipeline.py",
        pipeline_owns_close_logic,
    ),
]

fails = []
for pattern, description, predicate in CLAIMS:
    supported = predicate()
    rx = re.compile(pattern, re.I)
    for lesson in sorted(LESSONS.glob("*.md")):
        for n, line in enumerate(lesson.read_text().splitlines(), 1):
            if rx.search(line) and not supported:
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
