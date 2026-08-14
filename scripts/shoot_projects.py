#!/usr/bin/env python3
"""Capture front-page screenshots for the Projects page.

Deliberately NOT run in CI. Screenshots are committed artifacts; regenerating
them on every build would mean the site silently changes whenever someone
else's homepage changes. Run this by hand when a project's front page has
actually changed, review the diff, commit.

Usage:  python3 scripts/shoot_projects.py
Output: public/projects/<slug>.webp  (1280x800 viewport, above-the-fold only)

WebP, not PNG. These are screenshots of text-heavy pages, which is the worst
case for PNG: the blog capture was 1.34 MB as a 2x PNG and is 159 KB as WebP
at q=82, with aigregator at 175 KB. An 8x reduction with no visible loss at
card size. Shipping a 1.3 MB image on a page nobody scrolls to would be its
own small hypocrisy on a site about measuring what things cost.

Above-the-fold on purpose: a full-page capture of a blog index is a tall
ribbon that renders as an unreadable sliver in a card. The card is a visual
cue for "this is what that site looks like", not a document.
"""
import io
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "projects"

SHOTS = [
    ("blog", "https://blog.brianbaldock.net/"),
    ("aigregator", "https://aigregator.news/"),
]

# Both target sites honour prefers-color-scheme and default to dark when the
# OS asks for it. Forcing dark keeps the two cards visually consistent with
# each other and with this site's default theme.
def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 800},
            device_scale_factor=2,
            color_scheme="dark",
        )
        for slug, url in SHOTS:
            page = ctx.new_page()
            try:
                resp = page.goto(url, wait_until="networkidle", timeout=45000)
                status = resp.status if resp else 0
                if status >= 400:
                    failures.append(f"{slug}: HTTP {status} from {url}")
                    continue
                page.wait_for_timeout(1500)  # let webfonts settle
                dest = OUT / f"{slug}.webp"
                raw = page.screenshot(type="png")
                img = Image.open(io.BytesIO(raw)).convert("RGB")
                img.save(dest, "WEBP", quality=82, method=6)
                kb = dest.stat().st_size / 1024
                print(f"  [{status}] {slug:12} -> {dest.relative_to(ROOT)} ({kb:.0f} KB)")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{slug}: {exc}")
            finally:
                page.close()
        browser.close()

    if failures:
        print("\nSCREENSHOT FAILURES:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nAll screenshots captured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
