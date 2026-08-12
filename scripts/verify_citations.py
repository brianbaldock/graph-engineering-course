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
# The footer links Brian's other work. Same rule applies: a site that
# lectures readers about verification does not get to ship dead links.
PROJECTS = ROOT / "src/components/OtherProjects.astro"
if PROJECTS.exists():
    urls = re.findall(r"url:\s*'([^']+)'", PROJECTS.read_text())
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
