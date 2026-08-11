#!/usr/bin/env python3
"""End-to-end pipeline demo.

    python -m graphlab.pipeline

Runs the full architecture on the sample corpus:

    episode -> extract -> VALIDATE -> graph write -> retrieve subgraph
            -> grounded context -> (your model reasons here)

No API key. No server. Everything you see printed was computed.
"""

from __future__ import annotations

import sys

from .extract import RegexExtractor
from .sample_data import ALIASES, EPISODES, KNOWN_PEOPLE
from .store import GraphStore, render_context
from .validate import commit, validate


def build(db: str = ":memory:", verbose: bool = True) -> GraphStore:
    store = GraphStore(db)
    for alias, canonical in ALIASES.items():
        store.add_alias(alias, canonical)

    extractor = RegexExtractor(known_people=KNOWN_PEOPLE)
    total_rejected = 0

    for ep in EPISODES:
        eid = store.add_episode(ep["source"], ep["body"], ep["occurred_at"])
        payload = extractor.extract(ep["body"], ep["occurred_at"])

        # Temporal closes are handled before the gate: "X left Y" means
        # close the open edge, not create a new one.
        closes = [e for e in payload["edges"] if e.get("_close")]
        payload["edges"] = [e for e in payload["edges"] if not e.get("_close")]
        for c in closes:
            n = store.invalidate(c["source"], c["relation"], c["target"], c["_close"])
            if verbose and n:
                print(f"  ⏳ closed {n} edge(s): {c['source']} works_at {c['target']} until {c['_close']}")

        result = commit(store, payload, episode_id=eid)
        total_rejected += len(result.rejected)
        if verbose:
            print(f"[{ep['source']}] {result.report().splitlines()[0]}")
            for reason, item in result.rejected:
                print(f"    ✗ {reason}: {item}")

    if verbose:
        print(f"\nGraph: {store.stats()}")
        print(f"Rejected by the validation gate: {total_rejected}")
    return store


def demo_queries(store: GraphStore) -> None:
    print("\n" + "=" * 68)
    print("SELECTIVE RETRIEVAL — the whole graph is never sent to the model")
    print("=" * 68)

    q1 = "Where did Alice work when Project Atlas started?"
    edges = store.subgraph(["Alice"], hops=1, as_of="2024-06")
    print("\n" + render_context(edges, q1))

    q2 = "Where does Alice work now?"
    edges = store.subgraph(["Alice"], hops=1, as_of="2026-06")
    print("\n" + render_context(edges, q2))

    q3 = "What does Project Atlas transitively depend on?"
    edges = store.subgraph(["Project Atlas"], hops=2, max_edges=20)
    print("\n" + render_context(edges, q3))

    full = store.stats()["edges"]
    sent = len(edges)
    print(f"\nContext economy: sent {sent} of {full} edges "
          f"({100 * sent / full:.0f}% of the graph) for the widest query.")


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else ":memory:"
    demo_queries(build(db))
