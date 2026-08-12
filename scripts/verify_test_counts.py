"""Fail if a lesson publishes a test count that no longer matches reality.

Two lessons shipped "15 passed" long after the suite reached 20. The README
said 20. A course whose thesis is "we ran every command" cannot have its own
artifacts disagree about what the command prints.

So don't trust prose. Run the suite, read the number, compare.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABS = ROOT / "labs"
PY = LABS / ".venv/bin/python"
if not PY.exists():
    PY = Path(sys.executable)

r = subprocess.run(
    [str(PY), "-m", "pytest", "tests/", "-q"],
    cwd=LABS, capture_output=True, text=True,
)
# A failing suite must not silently become the new "truth". If pytest exits
# non-zero, the count it printed is not something to sync prose against.
if r.returncode != 0:
    print(f"pytest exited {r.returncode}; refusing to validate counts against a failing suite.")
    print(r.stdout[-1200:])
    sys.exit(1)

m = re.search(r"(\d+) passed", r.stdout)
if not m:
    print("could not determine the real test count:")
    print(r.stdout[-800:])
    sys.exit(1)
actual = int(m.group(1))
print(f"actual suite: {actual} passed")

targets = list((ROOT / "src/content/lessons").glob("*.md")) + [ROOT / "README.md"]
if not targets:
    sys.exit("FAIL: no lessons or README found. Nothing was verified.")

# Any number sitting next to the word "test", plus pytest's own summary line.
#
# The first version of this script listed specific phrasings and kept
# missing new ones: it passed while "15 passing tests" sat in Lesson 11 and
# "20 tests" sat in the README. Guessing at phrasings is the wrong shape for
# this check. Match structurally instead and let the exclusions below carve
# out the numbers that legitimately are not suite totals.
COUNT_NEAR_TEST = re.compile(
    r"(?<![\w.])(\d{1,4})\s+(?:\w+\s+){0,2}?tests?\b"   # "22 tests", "15 passing tests"
    r"|(?<![\w.])(\d{1,4})\s+passed\b"                   # "22 passed", incl. pytest output
    r"|suite of\s+(\d{1,4})\b",                          # "a suite of 19"
    re.I,
)

# Numbers near "test" that are NOT the suite total. Anything matching these
# is skipped rather than reported.
#
# Deliberately narrow. An earlier draft excluded any line containing a
# duration, which silently swallowed pytest's own "7 passed in 0.10s" and
# reopened the exact hole this script exists to close.
NOT_A_SUITE_TOTAL = re.compile(
    r"\b(?:python|astro|node|version|v)\s*\d+\.\d"  # "Python 3.10 for the tests"
    r"|\btest\s*\d+\b",                             # "test 3"
    re.I,
)

fails = []
for f in targets:
    text = f.read_text()
    for line_no, line in enumerate(text.splitlines(), 1):
        if NOT_A_SUITE_TOTAL.search(line):
            continue
        for m in COUNT_NEAR_TEST.finditer(line):
            claimed = int(m.group(1) or m.group(2) or m.group(3))
            if claimed != actual:
                fails.append(
                    f"{f.relative_to(ROOT)}:{line_no}: claims '{m.group(0).strip()}', "
                    f"actual suite is {actual}"
                )

if fails:
    print("\nPUBLISHED TEST COUNTS OUT OF DATE:")
    for x in fails:
        print(f"  {x}")
    sys.exit(1)

print("All published test counts match the suite.")
