"""Verify analytics + feedback actually shipped into the built HTML.

The GoatCounter failure mode is silent: if Astro bundles the script, the
data-goatcounter attribute is stripped and you get zero pageviews forever
with no error. So assert on the built artifact, not on the source.
"""
import pathlib
import sys

DIST = pathlib.Path("/home/brian/projects/graph-engineering-course/dist")
pages = sorted(DIST.rglob("index.html"))
lesson_pages = [p for p in pages if "/lessons/" in str(p) and p.parent.name != "lessons"]

fails = []

# 1. GoatCounter beacon on EVERY page, with the attribute intact.
missing_gc = [
    p.relative_to(DIST)
    for p in pages
    if 'data-goatcounter="https://agenticgraphs.goatcounter.com/count"' not in p.read_text()
    or "gc.zgo.at/count.js" not in p.read_text()
]
if missing_gc:
    fails.append(f"GoatCounter beacon missing/mangled on {len(missing_gc)} page(s): {missing_gc[:5]}")

# 2. giscus on every lesson page, with the real verified IDs.
for p in lesson_pages:
    t = p.read_text()
    for needle in (
        "giscus.app/client.js",
        "brianbaldock/graph-engineering-course",
        "R_kgDOT1iL_A",
        "DIC_kwDOT1iL_M4DDLTX",
        'id="giscus-container"',
    ):
        if needle not in t:
            fails.append(f"{p.relative_to(DIST)}: missing giscus bit {needle!r}")
            break

# 3. giscus must NOT be on non-lesson pages (index, setup, 404, lessons index).
non_lesson = [p for p in pages if p not in lesson_pages]
leaked = [p.relative_to(DIST) for p in non_lesson if "giscus-container" in p.read_text()]
if leaked:
    fails.append(f"giscus leaked onto non-lesson pages: {leaked}")

print(f"pages checked:        {len(pages)}")
print(f"lesson pages:         {len(lesson_pages)}")
print(f"GoatCounter present:  {len(pages) - len(missing_gc)}/{len(pages)}")
print(f"giscus on lessons:    {len(lesson_pages) - sum(1 for f in fails if 'missing giscus' in f)}/{len(lesson_pages)}")
print(f"giscus leak check:    {'clean' if not leaked else 'LEAKED'}")

if fails:
    print("\nFAILURES:")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("\nAnalytics and feedback verified in built output.")
