#!/usr/bin/env python3
"""Word budget, split by prose versus fenced code and frontmatter.

The 900-1400 budget was set for readable prose. Counting fenced code
against it penalises exactly the lessons that show their work, which is
the opposite of what this course wants. Report both so the decision is
made on real numbers.
"""
import pathlib
import re

LESSONS = sorted(pathlib.Path("src/content/lessons").glob("*.md"))
print(f"{'lesson':<34}{'prose':>7}{'code':>7}{'total':>7}  {'prose verdict':<12}")
print("-" * 74)

for path in LESSONS:
    text = path.read_text()
    body = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)

    code_words = 0
    for block in re.findall(r"```.*?```", body, flags=re.S):
        code_words += len(block.split())

    prose = re.sub(r"```.*?```", "", body, flags=re.S)
    prose = re.sub(r"<[^>]+>", " ", prose)
    prose_words = len(prose.split())

    total = prose_words + code_words
    if prose_words < 900:
        verdict = "under 900"
    elif prose_words > 1400:
        verdict = "OVER 1400"
    else:
        verdict = "ok"
    print(f"{path.name:<34}{prose_words:>7}{code_words:>7}{total:>7}  {verdict:<12}")
