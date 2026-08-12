"""The single ingestion boundary.

Every write into the graph goes through here: the pipeline demo, the MCP
server, and anything you build on top. That is the point. When the MCP
server had its own copy of this logic it quietly dropped temporal closes,
so an agent that learned "Alice left Northwind" left the old employment
edge open forever and the graph reported two current employers.

One semantic boundary, one behaviour. If you add a write path, call this.
"""

from __future__ import annotations

from .extract import RegexExtractor
from .validate import commit


def ingest_episode(
    store,
    text: str,
    source: str = "agent",
    occurred_at: str | None = None,
    extractor=None,
):
    """Add one episode to the graph: extract, close, validate, write.

    Returns (episode_id, ValidationResult, closed_edge_count).

    The close step runs BEFORE the gate on purpose. "Alice left Northwind"
    is not a new fact to add, it is an instruction to bound an existing
    one. Treating it as a normal edge is how a graph ends up asserting
    that someone works at two companies at once.
    """
    if extractor is None:
        extractor = RegexExtractor()

    episode_id = store.add_episode(source, text, occurred_at)
    payload = extractor.extract(text, occurred_at)

    closes = [e for e in payload["edges"] if e.get("_close")]
    payload["edges"] = [e for e in payload["edges"] if not e.get("_close")]

    closed = 0
    for c in closes:
        closed += store.invalidate(
            c["source"], c["relation"], c["target"], c["_close"]
        )

    result = commit(store, payload, episode_id=episode_id)
    return episode_id, result, closed
