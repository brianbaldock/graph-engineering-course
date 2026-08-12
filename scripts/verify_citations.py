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

fails = []
for key, entry in data.items():
    for field in REQUIRED:
        if field not in entry:
            fails.append(f"{key}: missing required field '{field}'")
    if not entry.get("supports"):
        fails.append(f"{key}: 'supports' is empty; a source with no claim is decoration")

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
