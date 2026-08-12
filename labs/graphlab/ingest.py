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

    # Detect closes by KEY PRESENCE, not truthiness.
    #
    # The extractor marks a departure with {"_close": <date>}. When the
    # text carries no date and the caller passed no occurred_at, that
    # value is None. Testing `e.get("_close")` then reads falsy, the
    # close silently falls through to the normal edge list, and
    # "Alice left Northwind" gets written as a SECOND open works_at
    # edge. The graph ends up asserting the exact contradiction this
    # boundary exists to prevent, and reports "accepted" while doing it.
    closes = [e for e in payload["edges"] if "_close" in e]
    payload["edges"] = [e for e in payload["edges"] if "_close" not in e]

    closed = 0
    undated_closes = []
    for c in closes:
        when = c.get("_close")
        if not when:
            # No date anywhere: not enough information to bound the fact.
            # Refuse rather than guess. Writing it as a new open edge is
            # worse than refusing, and silently dropping it is worse than
            # saying so.
            undated_closes.append(f"{c['source']} {c['relation']} {c['target']}")
            continue
        closed += store.invalidate(c["source"], c["relation"], c["target"], when)

    result = commit(store, payload, episode_id=episode_id)
    for item in undated_closes:
        result.rejected.append(("close_without_date", item))
    return episode_id, result, closed
