#!/usr/bin/env python3
"""Report lesson length, split by prose versus fenced code and frontmatter.

This is a REPORT. It has no thresholds, no verdicts, and never fails the
build. It exists so a length change is visible in a CI log, not so anything
gets cut to hit a number.

History, because the number mattered more than it should have. A "900-1400
words" range started life as a drafting hint inside a subagent prompt, meant
to stop generated drafts padding. Nobody asked for it, it appeared nowhere on
the published site, and its CI step never failed the build. It still got
treated as a standard: a round of edits cut real explanatory material out of
Lesson 0 to satisfy it, including the sentence connecting the two halves of
the course.

Brian retired it explicitly on 2026-08-14: the limit was fabricated for an
unrelated purpose and should not constrain future work. So the thresholds are
gone rather than merely widened. A lesson is as long as it earns.

Prose and fenced code are still counted separately, because counting code
against a length figure penalises exactly the lessons that show their work.
"""
import pathlib
import re

LESSONS = sorted(pathlib.Path("src/content/lessons").glob("*.md"))
print(f"{'lesson':<34}{'prose':>7}{'code':>7}{'total':>7}")
print("-" * 60)

totals = [0, 0]
for path in LESSONS:
    text = path.read_text()
    body = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)

    code_words = 0
    for block in re.findall(r"```.*?```", body, flags=re.S):
        code_words += len(block.split())

    prose = re.sub(r"```.*?```", "", body, flags=re.S)
    prose = re.sub(r"<[^>]+>", " ", prose)
    prose_words = len(prose.split())

    totals[0] += prose_words
    totals[1] += code_words
    print(f"{path.name:<34}{prose_words:>7}{code_words:>7}{prose_words + code_words:>7}")

print("-" * 60)
print(f"{'course total':<34}{totals[0]:>7}{totals[1]:>7}{sum(totals):>7}")
