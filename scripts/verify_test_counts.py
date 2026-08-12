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
m = re.search(r"(\d+) passed", r.stdout)
if not m:
    print("could not determine the real test count:")
    print(r.stdout[-800:])
    sys.exit(1)
actual = int(m.group(1))
print(f"actual suite: {actual} passed")

targets = list((ROOT / "src/content/lessons").glob("*.md")) + [ROOT / "README.md"]
fails = []
for f in targets:
    text = f.read_text()
    for claimed in re.findall(r"(\d+) passed", text):
        if int(claimed) != actual:
            fails.append(f"{f.relative_to(ROOT)}: publishes '{claimed} passed', actual is {actual}")
    # also catch prose like "those 15 tests"
    for claimed in re.findall(r"those (\d+) tests", text):
        if int(claimed) != actual:
            fails.append(f"{f.relative_to(ROOT)}: prose says 'those {claimed} tests', actual is {actual}")

if fails:
    print("\nPUBLISHED TEST COUNTS OUT OF DATE:")
    for x in fails:
        print(f"  {x}")
    sys.exit(1)

print("All published test counts match the suite.")
