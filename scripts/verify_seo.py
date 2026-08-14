"""Validate the JSON-LD and SEO tags in the built site.

Parses every ld+json block out of dist/ and fails loudly if one is malformed,
missing required fields, or points at a non-production URL. Structured data
that does not parse is worse than none: it looks present and does nothing.
"""
import json
import re
import sys
from pathlib import Path

DIST = Path(__file__).resolve().parent.parent / "dist"
SITE = "https://agenticgraphs.dev"

LD = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.S)
# Counting the opening tags separately is deliberate. If a malformed block
# breaks the non-greedy body match, the findall count silently drops and the
# checker would report success having validated nothing. Comparing the two
# counts turns that silent skip into a failure.
LD_OPEN = re.compile(r'<script type="application/ld\+json">')
CANON = re.compile(r'<link rel="canonical" href="([^"]+)"')

failures: list[str] = []
pages = sorted(DIST.rglob("*.html"))
if not pages:
    sys.exit("FAIL: no HTML in dist/. Run npm run build first.")

lessons_with_ld = 0
for page in pages:
    rel = page.relative_to(DIST)
    html = page.read_text(encoding="utf-8")

    canon = CANON.search(html)
    if not canon:
        failures.append(f"{rel}: no canonical link")
    elif not canon.group(1).startswith(SITE):
        failures.append(f"{rel}: canonical is not production: {canon.group(1)}")

    blocks = LD.findall(html)
    declared = len(LD_OPEN.findall(html))
    if declared != len(blocks):
        failures.append(
            f"{rel}: {declared} ld+json tag(s) but only {len(blocks)} parsed out; "
            "a block is malformed or unterminated")
    for raw in blocks:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            failures.append(f"{rel}: ld+json does not parse: {exc}")
            continue
        if "@context" not in data or "@type" not in data:
            failures.append(f"{rel}: ld+json missing @context/@type")
            continue
        for url_field in ("url",):
            if url_field in data and not str(data[url_field]).startswith(SITE):
                failures.append(
                    f"{rel}: ld+json {url_field} not production: {data[url_field]}")
        if data["@type"] == "LearningResource":
            lessons_with_ld += 1
            for req in ("name", "description", "timeRequired", "isPartOf"):
                if not data.get(req):
                    failures.append(f"{rel}: LearningResource missing {req}")
        if data["@type"] == "Course":
            sections = data.get("syllabusSections") or []
            if len(sections) < 10:
                failures.append(
                    f"{rel}: Course syllabus has {len(sections)} sections, expected all lessons")

lesson_pages = [p for p in pages if p.parent.parent.name == "lessons"]
if lessons_with_ld != len(lesson_pages):
    failures.append(
        f"lesson JSON-LD coverage: {lessons_with_ld} of {len(lesson_pages)} lesson pages")

robots = DIST / "robots.txt"
if not robots.exists():
    failures.append("dist/robots.txt missing")
elif "Sitemap:" not in robots.read_text(encoding="utf-8"):
    failures.append("robots.txt does not advertise the sitemap")

if not (DIST / "sitemap-index.xml").exists():
    failures.append("dist/sitemap-index.xml missing")

if failures:
    print("SEO metadata check FAILED:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)

print(f"SEO metadata OK: {len(pages)} pages, "
      f"{lessons_with_ld} lesson JSON-LD blocks, canonical + robots + sitemap present.")
