#!/usr/bin/env python3
"""Import the hand-made cover art into the site's public/ directory.

Source lives in Brian's Obsidian vault (the vault is the authoring surface;
the repo gets derived, optimized copies). Rerun this after regenerating the
covers, review the diff, commit.

Two different jobs, two different outputs, because they have different
constraints:

  cover-{dark,light}.webp   On-page hero. WebP because it is a browser
                            surface and the source PNGs are ~1 MB each,
                            which is absurd for decoration.

  og-cover.png              Social card (LinkedIn, X, Bluesky, Discord).
                            Stays PNG: several scrapers still do not render
                            WebP OG images, and a broken preview on the exact
                            post announcing the site is not a risk worth
                            taking for a few KB.

OG sizing note: the source is 16:9 (1.777) and the OG spec wants 1.91:1.
Rather than letterbox (bars look broken in a LinkedIn card) this crops
symmetrically off the top and bottom, which is empty background in this
design. Verified against actual pixels rather than assumed: a throwaway probe
scanned for rows deviating from the corner background colour and found content
only in rows 230..853 of 941, in both the light and dark source art, while
this crop removes 31 from the top and 32 from the bottom. Roughly 200px of
clearance on each side. Re-run that check if the cover art is ever redrawn,
because the safety margin is a property of the artwork, not of this script.
"""
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
VAULT = Path(
    "/home/brian/Documents/Obsidian Vault/Projects/Newsletters/Field Notes/"
    "001-the-gate-that-verified-nothing/Assets"
)

OG_W, OG_H = 1200, 630


def main() -> int:
    missing = [n for n in ("cover-dark.png", "cover-light.png") if not (VAULT / n).exists()]
    if missing:
        print(f"MISSING in vault: {missing}")
        print(f"  looked in: {VAULT}")
        print("  Run: cd '/home/brian/Documents/Obsidian Vault' && git pull --rebase")
        return 1

    for theme in ("dark", "light"):
        src = VAULT / f"cover-{theme}.png"
        img = Image.open(src).convert("RGB")
        dest = PUBLIC / f"cover-{theme}.webp"
        img.save(dest, "WEBP", quality=88, method=6)
        print(f"  hero  {theme:5} {img.size} -> {dest.name} "
              f"({dest.stat().st_size / 1024:.0f} KB, was "
              f"{src.stat().st_size / 1024:.0f} KB)")

    # Social card from the dark cover: it is the site's default theme and the
    # one that reads best against both LinkedIn's white feed and Discord's
    # dark one.
    img = Image.open(VAULT / "cover-dark.png").convert("RGB")
    w, h = img.size
    target_h = round(w / (OG_W / OG_H))
    if target_h > h:
        print(f"REFUSING: source {w}x{h} is too tall-safe to crop to OG ratio")
        return 1
    off = (h - target_h) // 2
    og = img.crop((0, off, w, off + target_h)).resize((OG_W, OG_H), Image.LANCZOS)
    og_dest = PUBLIC / "og-cover.png"
    og.save(og_dest, "PNG", optimize=True)
    print(f"  og    crop {h}->{target_h} (-{off}px top/bottom) -> {og_dest.name} "
          f"({og_dest.stat().st_size / 1024:.0f} KB)")

    print("\nCovers imported.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
