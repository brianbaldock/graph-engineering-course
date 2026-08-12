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

# Every way the prose might state a count. The first version of this script
# checked two patterns and reported success while "all 20 tests" sat stale in
# the wrap-up lesson.
PATTERNS = [
    r"(\d+) passed",
    r"those (\d+) tests",
    r"all (\d+) tests",
    r"(\d+) tests pass",
    r"(\d+) passing tests",
    r"suite of (\d+)",
    r"(\d+) tests in",
]

fails = []
for f in targets:
    text = f.read_text()
    for pat in PATTERNS:
        for claimed in re.findall(pat, text):
            if int(claimed) != actual:
                fails.append(
                    f"{f.relative_to(ROOT)}: claims '{claimed}' via /{pat}/, actual is {actual}"
                )

if fails:
    print("\nPUBLISHED TEST COUNTS OUT OF DATE:")
    for x in fails:
        print(f"  {x}")
    sys.exit(1)

print("All published test counts match the suite.")
