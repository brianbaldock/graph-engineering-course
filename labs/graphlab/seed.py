#!/usr/bin/env python3
"""Seed the demo graph used by the MCP lesson.

    python -m graphlab.seed memory.db

Deliberately wipe-and-rebuild. Seeding twice into the same file would add
duplicate episodes and make the lesson's numbers drift from the printed
ones, so this removes an existing database first and says that it did.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .pipeline import build
from .store import GraphStore

EXPECTED = {"entities": 8, "edges": 9, "episodes": 5, "open_edges": 8, "aliases": 2}


def seed(path: str = "memory.db", verbose: bool = True) -> GraphStore:
    target = Path(path)
    if target.exists():
        target.unlink()
        if verbose:
            print(f"removed existing {target}")

    store = build(str(target), verbose=False)
    stats = store.stats()

    if verbose:
        print(f"seeded {target}: {stats}")
        if stats != EXPECTED:
            print(f"WARNING: expected {EXPECTED}")
    return store


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "memory.db"
    store = seed(db)
    if store.stats() != EXPECTED:
        raise SystemExit("seed did not produce the documented baseline")
