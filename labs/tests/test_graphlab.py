"""Tests for the graph lab. Run: python -m pytest tests/ -q  (from labs/)

These are the tests the course asks you to keep green while you extend
the store. They encode the invariants that matter:
  * the validation gate actually rejects bad extractions
  * temporal filtering returns the right answer for a given point in time
  * retrieval stays bounded
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graphlab.store import GraphStore, render_context
from graphlab.validate import validate, commit, normalize_name
from graphlab.extract import RegexExtractor
from graphlab.pipeline import build


# --------------------------------------------------------------- validation

def test_gate_rejects_unknown_relation():
    res = validate({
        "entities": [{"name": "A", "type": "person"}, {"name": "B", "type": "organization"}],
        "edges": [{"source": "A", "target": "B", "relation": "vibes_with"}],
    })
    assert res.edges == []
    assert any("not in allowed vocabulary" in r for r, _ in res.rejected)


def test_gate_rejects_ungrounded_edge():
    """The hallucination trap: an edge to an entity the payload never declared."""
    res = validate({
        "entities": [{"name": "A", "type": "person"}],
        "edges": [{"source": "A", "target": "Ghost Corp", "relation": "works_at"}],
    })
    assert res.edges == []
    assert any("undeclared entity" in r for r, _ in res.rejected)


def test_gate_rejects_bad_type_and_bad_date():
    res = validate({
        "entities": [{"name": "A", "type": "wizard"}, {"name": "B", "type": "organization"}],
        "edges": [],
    })
    assert any("not in schema" in r for r, _ in res.rejected)

    res2 = validate({
        "entities": [{"name": "A", "type": "person"}, {"name": "B", "type": "organization"}],
        "edges": [{"source": "A", "target": "B", "relation": "works_at", "valid_from": "last tuesday"}],
    })
    assert res2.edges == []
    assert any("not YYYY" in r for r, _ in res2.rejected)


def test_gate_rejects_self_edge():
    res = validate({
        "entities": [{"name": "A", "type": "person"}],
        "edges": [{"source": "A", "target": "A", "relation": "works_at"}],
    })
    assert any("self-referential" in r for r, _ in res.rejected)


def test_normalization_collapses_corporate_suffix():
    assert normalize_name("Apple Inc.") == "Apple"
    assert normalize_name("  Northwind   LLC ") == "Northwind"


def test_relation_normalization_accepts_loose_input():
    res = validate({
        "entities": [{"name": "A", "type": "person"}, {"name": "B", "type": "organization"}],
        "edges": [{"source": "A", "target": "B", "relation": "Works At"}],
    })
    assert len(res.edges) == 1 and res.edges[0]["relation"] == "works_at"


def test_commit_writes_only_valid_rows():
    g = GraphStore()
    res = commit(g, {
        "entities": [{"name": "A", "type": "person"}, {"name": "B", "type": "organization"}],
        "edges": [
            {"source": "A", "target": "B", "relation": "works_at"},
            {"source": "A", "target": "Nope", "relation": "works_at"},
        ],
    })
    assert g.stats()["edges"] == 1
    assert len(res.rejected) == 1


# ----------------------------------------------------------------- temporal

def test_temporal_query_returns_the_right_employer():
    g = GraphStore()
    g.upsert_entity("Alice", "person")
    g.upsert_entity("X", "organization")
    g.upsert_entity("Y", "organization")
    g.add_edge("Alice", "works_at", "X", valid_from="2024", valid_until="2026")
    g.add_edge("Alice", "works_at", "Y", valid_from="2026")

    at_2025 = {e.target for e in g.edges_of("Alice", as_of="2025")}
    at_2027 = {e.target for e in g.edges_of("Alice", as_of="2027")}
    assert at_2025 == {"X"}
    assert at_2027 == {"Y"}


def test_invalidate_closes_open_edge_only():
    g = GraphStore()
    g.upsert_entity("A", "person")
    g.upsert_entity("B", "organization")
    g.add_edge("A", "works_at", "B", valid_from="2020")
    assert g.invalidate("A", "works_at", "B", "2024") == 1
    assert g.invalidate("A", "works_at", "B", "2025") == 0  # already closed


# ---------------------------------------------------------------- retrieval

def test_subgraph_is_bounded_by_max_edges():
    g = GraphStore()
    g.upsert_entity("hub", "service")
    for i in range(50):
        g.upsert_entity(f"n{i}", "service")
        g.add_edge("hub", "depends_on", f"n{i}")
    assert len(g.subgraph(["hub"], hops=1, max_edges=10)) <= 10


def test_alias_resolution_merges_nodes():
    g = GraphStore()
    g.add_alias("Northwind Inc", "Northwind")
    g.upsert_entity("Northwind", "organization")
    g.upsert_entity("Northwind Inc", "organization")
    assert g.stats()["entities"] == 1


def test_edges_carry_provenance_for_citation():
    g = GraphStore()
    eid = g.add_episode("doc", "body", "2025-01-01")
    g.upsert_entity("A", "person")
    g.upsert_entity("B", "organization")
    g.add_edge("A", "works_at", "B", valid_from="2025", episode_id=eid)
    edge = g.edges_of("A")[0]
    assert edge.episode_id == eid
    assert "episode" in edge.cite()


def test_render_context_includes_every_edge():
    g = build(verbose=False)
    edges = g.subgraph(["Alice"], hops=1)
    ctx = render_context(edges, "test?")
    for e in edges:
        assert e.cite() in ctx


# ---------------------------------------------------------------- pipeline

def test_full_pipeline_produces_a_temporally_correct_graph():
    g = build(verbose=False)
    s = g.stats()
    assert s["episodes"] == 5 and s["edges"] > 5

    then = {e.target for e in g.edges_of("Alice", as_of="2024-06") if e.relation == "works_at"}
    now = {e.target for e in g.edges_of("Alice", as_of="2026-06") if e.relation == "works_at"}
    assert then == {"Northwind"}
    assert now == {"Contoso"}


def test_extractor_is_deterministic():
    x = RegexExtractor(known_people={"Alice"})
    a = x.extract("Alice joined Northwind 2024.", "2024-01-01")
    b = x.extract("Alice joined Northwind 2024.", "2024-01-01")
    assert a == b
