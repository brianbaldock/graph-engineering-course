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


def store_edge_count(srv, name):
    """Edges around an entity, read straight from the store.

    Deliberately bypasses get_subgraph: this is the unclamped ground truth
    the endpoint's output gets compared against.
    """
    return len(srv.store.edges_of(name))


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

    # Assert the clamp by ARTIFACT, not by status string.
    #
    # The previous version of this check was `assert capped`, which only
    # proved the call returned something non-empty. Deleting the clamp
    # entirely left this verifier printing "clamped" and exiting 0. That
    # is the exact failure Lesson 0 warns about: trusting a success
    # message instead of the thing it claims to describe. So compare the
    # clamped call against the policy's own caps and against an
    # explicitly over-large request.
    from graphlab.policy import clamp, load_policy, retrieval_caps

    caps = retrieval_caps(load_policy())
    asked_hops, asked_edges = 99, 10_000
    got_hops, got_edges = clamp(asked_hops, asked_edges)
    assert got_hops == caps["max_hops"], f"hops not clamped: {got_hops} != {caps['max_hops']}"
    assert got_edges == caps["max_edges"], f"max_edges not clamped: {got_edges} != {caps['max_edges']}"

    # Proving clamp() works is not the same as proving the ENDPOINT uses it.
    # An earlier version of this check only exercised the helper, so removing
    # the clamp call from get_subgraph left the verifier green.
    #
    # To assert on the endpoint we need a graph big enough that the cap
    # actually binds: more than max_edges edges within reach of one hop.
    # Otherwise both the clamped and unclamped calls return the same handful
    # of rows and the check proves nothing.
    n_peers = caps["max_edges"] + 20
    for i in range(n_peers):
        srv.add_knowledge(f"Alice uses Service{i:03d}.", "verify", "2026-05-01")

    unbounded = store_edge_count(srv, "Alice")
    assert unbounded > caps["max_edges"], (
        f"test graph has only {unbounded} edges around Alice; it must exceed "
        f"the {caps['max_edges']} cap or this assertion cannot detect anything"
    )

    wide = srv.get_subgraph(["Alice"], hops=asked_hops, max_edges=asked_edges)
    edge_lines = [ln for ln in wide.splitlines() if "-->" in ln]
    assert len(edge_lines) <= caps["max_edges"], (
        f"endpoint returned {len(edge_lines)} edges against a {caps['max_edges']} "
        f"cap: the clamp is not wired into get_subgraph"
    )
    print(
        f"retrieval clamped by artifact: {unbounded} edges exist around Alice, "
        f"asked for {asked_edges} at {asked_hops} hops, "
        f"endpoint returned {len(edge_lines)} (cap {caps['max_edges']})"
    )

    print("\nOK: MCP server loads, enforces policy caps, and closes expired facts.")
