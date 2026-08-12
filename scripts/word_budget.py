#!/usr/bin/env python3
"""Report lesson length, split by prose versus fenced code and frontmatter.

This is a REPORT, not a gate. It never fails the build.

History worth knowing before you act on these numbers. The 900-1400 range
started life as a drafting hint in a subagent prompt ("900-1400 words each,
substance over padding") to stop generated lessons padding. It was never a
publishing standard, and it appears nowhere on the site. It later got
treated as a hard target, and a round of edits cut real explanatory
material out of Lesson 0 to hit it, including the sentence that explained
how the two halves of the course connect.

So: a lesson over the range is a prompt to re-read it, not an instruction
to cut. Clarity wins over the number every time. If a lesson is long
because it earns the length, leave it alone.

Counting fenced code against the range penalises exactly the lessons that
show their work, which is why prose and code are reported separately.
"""
import pathlib
import re

LESSONS = sorted(pathlib.Path("src/content/lessons").glob("*.md"))
print(f"{'lesson':<34}{'prose':>7}{'code':>7}{'total':>7}  {'prose note':<12}")
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
        verdict = "short"
    elif prose_words > 1400:
        verdict = "long, check"
    else:
        verdict = "ok"
    print(f"{path.name:<34}{prose_words:>7}{code_words:>7}{total:>7}  {verdict:<12}")
