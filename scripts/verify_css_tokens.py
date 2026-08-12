"""Find CSS custom properties that are USED but never DEFINED.

Root cause of the pa11y failure: var(--text-muted, #9a9a9a) referenced a
token defined nowhere, so the hardcoded fallback silently won and ignored
both themes. That is invisible in review and only surfaces as a contrast
failure on one theme.

Sweep the whole source tree for the same shape.
"""
import re
import sys
from pathlib import Path

SRC = Path("/home/brian/projects/graph-engineering-course/src")

defined = set()
used = {}

for f in list(SRC.rglob("*.astro")) + list(SRC.rglob("*.css")):
    text = f.read_text()
    for m in re.finditer(r"(--[\w-]+)\s*:", text):
        defined.add(m.group(1))
    for m in re.finditer(r"var\(\s*(--[\w-]+)\s*(,([^)]*))?\)", text):
        token, fallback = m.group(1), (m.group(3) or "").strip()
        used.setdefault(token, []).append((f.relative_to(SRC), fallback))

print(f"tokens defined: {len(defined)}")
print(f"tokens used:    {len(used)}")
print()

orphans = {t: v for t, v in used.items() if t not in defined}
if orphans:
    print("USED BUT NEVER DEFINED (fallback silently wins, ignores theme):")
    for token, sites in sorted(orphans.items()):
        for path, fallback in sites:
            fb = f"fallback {fallback!r}" if fallback else "NO FALLBACK"
            print(f"  {token:20} {str(path):34} {fb}")
    sys.exit(1)

print("No orphaned CSS tokens. Every var() resolves to a defined token.")
