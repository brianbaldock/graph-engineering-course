"""Verify every citation in src/data/sources.yaml actually resolves.

The course's own standard: a citation you have not checked is decoration.
This runs in CI so a dead link fails the build instead of quietly rotting.
"""
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "src/data/sources.yaml"

data = yaml.safe_load(SOURCES.read_text())
REQUIRED = ("title", "publisher", "url", "checked", "supports")

# A verifier that passes on an empty corpus verifies nothing. Same class of
# bug as the one that made verify_integrations.py green on CI while checking
# zero pages. Refuse to succeed with nothing to check.
if not data:
    sys.exit("FAIL: sources.yaml is empty. Nothing was verified.")

fails = []
for key, entry in data.items():
    for field in REQUIRED:
        if field not in entry:
            fails.append(f"{key}: missing required field '{field}'")
    if not entry.get("supports"):
        fails.append(f"{key}: 'supports' is empty; a source with no claim is decoration")
    # A checked date that is not a date is not a checked date.
    checked = str(entry.get("checked", ""))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", checked):
        fails.append(f"{key}: 'checked' must be YYYY-MM-DD, got {checked!r}")

# Every key a lesson cites must exist here, and every entry here should be
# cited by something. An unreferenced registry is decoration too.
LESSONS = ROOT / "src/content/lessons"
cited = set()
for f in sorted(LESSONS.glob("*.md")):
    fm = f.read_text().split("---")
    if len(fm) < 2:
        continue
    block = re.search(r"^sources:\s*\n((?:\s*-\s*\S+\n)+)", fm[1], re.M)
    if not block:
        continue
    for key in re.findall(r"-\s*(\S+)", block.group(1)):
        cited.add(key)
        if key not in data:
            fails.append(f"{f.name} cites unknown source key '{key}'")

orphans = set(data) - cited
if orphans:
    for o in sorted(orphans):
        fails.append(f"{o}: in the registry but no lesson cites it")

if not cited:
    fails.append("no lesson cites any source; the registry is decorative")

print(f"{len(data)} sources, {len(cited)} cited by lessons")

if fails:
    print("SCHEMA FAILURES:")
    for f in fails:
        print(f"  {f}")
    sys.exit(1)

print(f"{len(data)} sources, schema OK. Checking reachability...\n")

dead = []
for key, entry in data.items():
    url = entry["url"]
    # Some sources ARE a negative result. The claim "graphiti-mcp is not a
    # published package" is evidenced by a 404, so 404 is the passing
    # condition for that entry. Declare it explicitly rather than
    # special-casing it in code.
    want = str(entry.get("expect_status", "2xx"))
    r = subprocess.run(
        ["curl", "-sL", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "20", url],
        capture_output=True, text=True,
    )
    code = r.stdout.strip()
    ok = code.startswith("2") if want == "2xx" else code == want
    note = "" if want == "2xx" else f"  (expected {want})"
    print(f"  [{code}] {key:28} {url}{note}")
    if not ok:
        dead.append(f"{key} -> {url} (HTTP {code}, expected {want})")

if dead:
    print("\nDEAD CITATIONS:")
    for d in dead:
        print(f"  {d}")
    sys.exit(1)

print("\nAll citations resolve.")

# --- outbound project links ------------------------------------------
# The projects page links Brian's other work. Same rule applies: a site that
# lectures readers about verification does not get to ship dead links.
#
# This block used to be wrapped in `if PROJECTS.exists()`, which is fail-open:
# renaming or moving the file made the check silently pass having tested
# nothing. Same defect class as the CSS gate that scanned zero files. The path
# is now required, and a zero-URL parse is a failure rather than a quiet
# success, so a change to the data shape cannot disarm the check.
PROJECTS = ROOT / "src/pages/projects.astro"
if not PROJECTS.exists():
    print(f"\nMISSING: {PROJECTS.relative_to(ROOT)} (project link check cannot run)")
    sys.exit(1)
text = PROJECTS.read_text()
urls = re.findall(r"url:\s*'([^']+)'", text)
if not urls:
    print(f"\nNO PROJECT URLS parsed from {PROJECTS.relative_to(ROOT)}.")
    print("  The `url: '...'` field shape changed. Update this regex.")
    sys.exit(1)
print(f"\nChecking {len(urls)} project links...")
broken = []
for url in urls:
    r = subprocess.run(
        ["curl", "-sL", "-o", "/dev/null", "-w", "%{http_code}",
         "--max-time", "25", url],
        capture_output=True, text=True,
    )
    code = r.stdout.strip()
    print(f"  [{code}] {url}")
    if not code.startswith("2"):
        broken.append(f"{url} (HTTP {code})")
if broken:
    print("\nDEAD PROJECT LINKS:")
    for b in broken:
        print(f"  {b}")
    sys.exit(1)
print("All project links resolve.")
# --- local image artifacts -------------------------------------------
# Screenshots and covers are committed by hand, not generated at build time,
# so a forgotten `git add` would otherwise ship a page of broken images that
# still builds green. Existence plus a non-trivial size, since a 0-byte or
# truncated file is the realistic failure, not an absent one.
shots = re.findall(r"shot:\s*'([^']+)'", text)
if not shots:
    print("\nNO PROJECT SCREENSHOTS parsed. The `shot: '...'` field shape changed.")
    sys.exit(1)
required = shots + ["/og-cover.png", "/cover-dark.webp", "/cover-light.webp"]
print(f"\nChecking {len(required)} local image artifacts...")
missing = []
for rel in required:
    p = ROOT / "public" / rel.lstrip("/")
    size = p.stat().st_size if p.exists() else 0
    print(f"  [{size:>7} B] {rel}")
    if size < 1024:
        missing.append(f"{rel} ({'absent' if size == 0 else f'{size} B, truncated?'})")
if missing:
    print("\nMISSING OR EMPTY IMAGE ARTIFACTS:")
    for m in missing:
        print(f"  {m}")
    sys.exit(1)
print("All image artifacts present.")
