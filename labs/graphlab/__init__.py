"""
graphlab: a tiny temporal knowledge graph on SQLite.

No server, no cloud, no API key. This is the reference store used by the
Graph Engineering course labs. It is deliberately small enough to read in
one sitting and complete enough to demonstrate every architectural point
in the course:

  * entities and edges as first-class rows
  * temporal validity on edges (valid_from / valid_until)
  * provenance: every edge points back to the episode that produced it
  * a validation gate between extraction and the graph write
  * bounded subgraph retrieval (n-hop) instead of "send the whole graph"

Usage:
    from graphlab.store import GraphStore
    g = GraphStore("memory.db")
    g.upsert_entity("Alice", "person")
    g.add_edge("Alice", "works_at", "Company X", valid_from="2024-01")
"""

__all__ = ["GraphStore", "Entity", "Edge"]
