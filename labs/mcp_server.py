#!/usr/bin/env python3
"""graphlab MCP server: expose the course knowledge graph as agent memory.

Works with any MCP client. The course wires it into two:
  * Hermes Agent    (~/.hermes/config.yaml -> mcp_servers)
  * Copilot CLI     (copilot mcp add ...)

Run standalone:
    pip install mcp
    python mcp_server.py /path/to/memory.db

Design note: the tools exposed here are deliberately NOT "run arbitrary
query". They are the four operations the routing policy actually
sanctions. An MCP server is a policy surface, not just an API wrapper.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graphlab.ingest import ingest_episode
from graphlab.policy import clamp, load_policy
from graphlab.store import GraphStore, render_context

# Server class moved in MCP SDK 2.0: `mcp.server.fastmcp.FastMCP` became
# `mcp.server.mcpserver.MCPServer`. Support both so this file works on
# whichever generation the reader has installed.
try:
    from mcp.server.mcpserver import MCPServer as _Server   # mcp >= 2.0
except ImportError:  # pragma: no cover
    try:
        from mcp.server.fastmcp import FastMCP as _Server   # mcp 1.x
    except ImportError as exc:
        print(f"MCP import failed ({exc}). Install the SDK:  pip install mcp", file=sys.stderr)
        raise SystemExit(1)

DB_PATH = os.environ.get("GRAPHLAB_DB") or (sys.argv[1] if len(sys.argv) > 1 else "memory.db")

mcp = _Server("graphlab")
store = GraphStore(DB_PATH)
# Strict at startup. A server whose job is to bound an agent should refuse
# to boot on an unreadable policy rather than quietly serve wider limits
# than the operator wrote.
POLICY = load_policy(strict=True)


@mcp.tool()
def search_entities(term: str, limit: int = 10) -> str:
    """Find entities in the knowledge graph by name or description.

    Always call this FIRST to resolve what the user is talking about,
    before retrieving a subgraph.
    """
    found = store.search_entities(term, limit)
    if not found:
        return f"No entities matching '{term}'."
    return "\n".join(f"{e.name} ({e.type}) {e.description}".rstrip() for e in found)


@mcp.tool()
def get_subgraph(entities: list[str], hops: int = 1, as_of: str = "", max_edges: int = 60) -> str:
    """Retrieve the smallest relevant subgraph around some entities.

    entities: canonical names from search_entities
    hops:     1 for direct relationships, 2 for transitive. Never more.
    as_of:    optional YYYY[-MM[-DD]] to see the graph as it was then.

    hops and max_edges are clamped to routing_policy.yaml. Tool arguments
    arrive from a model, so they are untrusted input and get bounded here.
    """
    hops, max_edges = clamp(hops, max_edges, POLICY)
    edges = store.subgraph(entities, hops=hops, as_of=as_of or None, max_edges=max_edges)
    if not edges:
        return "No edges found. Do not invent relationships; report the gap."
    return render_context(edges)


@mcp.tool()
def add_knowledge(
    episode_text: str, source: str = "agent", occurred_at: str = ""
) -> str:
    """Store a new episode as validated graph memory.

    The text is extracted, validated, and only the surviving entities and
    edges are written. Rejections are reported back so the caller can see
    what did NOT make it in.

    Goes through the same ingestion boundary as the pipeline, which means
    temporal closes are applied. An episode saying someone left a company
    bounds the existing edge instead of leaving two open.
    """
    _eid, result, closed = ingest_episode(
        store,
        episode_text,
        source=source,
        occurred_at=occurred_at or None,
    )
    report = result.report()
    if closed:
        report += f"\nclosed {closed} edge(s) that this episode ended"
    return report


@mcp.tool()
def graph_stats() -> str:
    """Report the size and shape of the knowledge graph."""
    return ", ".join(f"{k}={v}" for k, v in store.stats().items())


if __name__ == "__main__":
    mcp.run(transport="stdio")
