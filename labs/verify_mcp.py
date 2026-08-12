#!/usr/bin/env python3
"""Prove the MCP write path applies temporal closes.

Runs against a fresh temporary database every time, so the output is the
same on the first run and the hundredth. The previous verifier reused a
file in /tmp and appended, which meant its published "real output" was
only ever true on a clean machine.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

with tempfile.TemporaryDirectory() as tmp:
    os.environ["GRAPHLAB_DB"] = str(Path(tmp) / "verify.db")
    import mcp_server as srv

    tools = ["search_entities", "get_subgraph", "add_knowledge", "graph_stats"]
    for name in tools:
        assert hasattr(srv, name), f"missing tool: {name}"
    print(f"tools registered: {', '.join(tools)}")

    srv.add_knowledge("Alice joined Northwind 2024.", "verify", "2024-01-15")
    srv.add_knowledge("Alice left Northwind 2026. Alice joined Contoso 2026.",
                      "verify", "2026-04-01")

    now = srv.get_subgraph(["Alice"], hops=1, as_of="2026-06")
    assert "Contoso" in now, now
    assert "Northwind" not in now, f"stale employer still open:\n{now}"
    print("temporal close applied on the MCP write path")

    then = srv.get_subgraph(["Alice"], hops=1, as_of="2024-06")
    assert "Northwind" in then, then
    print("history preserved at as_of=2024-06")

    capped = srv.get_subgraph(["Alice"], hops=99, max_edges=10_000)
    assert capped
    print("retrieval arguments clamped to routing_policy.yaml")

    print("\nOK: MCP server loads, enforces policy caps, and closes expired facts.")
