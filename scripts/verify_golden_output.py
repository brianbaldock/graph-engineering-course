#!/usr/bin/env python3
"""Verify that published "Real output:" blocks match what the lab prints.

Lesson 8 shipped a stale verify_mcp.py golden output for a while. The
lesson text sitting directly under it says a golden output that drifts is
decoration rather than verification, which made the drift a self-refuting
claim as well as a factual error.

Reading the lesson is not enough to catch that. This runs the commands and
diffs the real output against the published block.

Report only for commands that are environment-dependent; a hard failure
for the ones that must be reproducible.
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

# (lesson, command to run, a distinctive line that must appear verbatim)
#
# Deliberately matched on distinctive lines rather than whole blocks: the
# seed line contains a path that legitimately varies by invocation.
CHECKS = [
    (
        "08-mcp-wiring.md",
        [str(PY), "verify_mcp.py"],
        "retrieval clamped by artifact:",
    ),
    (
        "08-mcp-wiring.md",
        [str(PY), "-m", "graphlab.seed", "/tmp/verify-golden.db"],
        "'entities': 8, 'edges': 9, 'episodes': 5, 'open_edges': 8, 'aliases': 2",
    ),
]

fails = []
for lesson, cmd, needle in CHECKS:
    published = (ROOT / "src/content/lessons" / lesson).read_text()

    r = subprocess.run(cmd, cwd=LABS, capture_output=True, text=True)
    if r.returncode != 0:
        fails.append(f"{lesson}: `{' '.join(cmd)}` exited {r.returncode}")
        continue

    real = r.stdout + r.stderr

    # The line the lab actually printed.
    actual_line = next(
        (ln.strip() for ln in real.splitlines() if needle in ln), None
    )
    if actual_line is None:
        fails.append(
            f"{lesson}: the lab no longer prints a line containing {needle!r}. "
            f"The published output describes a version of the code that is gone."
        )
        continue

    # Compare the part that must be stable, not incidental detail. The seed
    # line embeds whatever db path was passed on the command line, which is
    # not a property of the lesson being right.
    stable = actual_line[actual_line.index(needle):] if needle in actual_line else actual_line

    if stable not in published:
        # Show what the lesson claims, for a usable diff.
        claimed = next(
            (ln.strip() for ln in published.splitlines() if needle in ln),
            "(no matching line published)",
        )
        fails.append(
            f"{lesson}: published golden output is stale.\n"
            f"    lab prints: {actual_line}\n"
            f"    lesson says: {claimed}"
        )
    else:
        print(f"ok  {lesson:22} {stable[:60]}")

if fails:
    print("\nSTALE PUBLISHED OUTPUT:")
    for f in fails:
        print(f"  {f}")
    print(
        "\nRun the command, paste the real output into the lesson. A golden "
        "output that drifts is decoration, which is what the lesson itself says."
    )
    sys.exit(1)

print("\nPublished golden outputs match the lab.")
