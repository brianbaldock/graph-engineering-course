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
from .ingest import ingest_episode
from .sample_data import ALIASES, EPISODES, KNOWN_PEOPLE
from .store import GraphStore, render_context


def build(db: str = ":memory:", verbose: bool = True) -> GraphStore:
    store = GraphStore(db)
    for alias, canonical in ALIASES.items():
        store.add_alias(alias, canonical)

    extractor = RegexExtractor(known_people=KNOWN_PEOPLE)
    total_rejected = 0

    for ep in EPISODES:
        # One shared ingestion boundary, used by the MCP server too.
        _eid, result, closed = ingest_episode(
            store,
            ep["body"],
            source=ep["source"],
            occurred_at=ep["occurred_at"],
            extractor=extractor,
        )

        if verbose and closed:
            print(f"  closed {closed} edge(s) that the episode ended")

        total_rejected += len(result.rejected)
        if verbose:
            print(f"[{ep['source']}] {result.report().splitlines()[0]}")
            for reason, item in result.rejected:
                print(f"    rejected {reason}: {item}")

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
