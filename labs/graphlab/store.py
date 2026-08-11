"""Temporal knowledge graph store backed by SQLite."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
    name        TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS aliases (
    -- No FK to entities: aliases are seeded BEFORE the canonical entity
    -- exists, which is the normal case when you know your vocabulary up
    -- front. Enforcing the FK here makes alias seeding impossible.
    alias     TEXT PRIMARY KEY,
    canonical TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS episodes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,
    occurred_at TEXT,
    body        TEXT NOT NULL,
    ingested_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS edges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL REFERENCES entities(name) ON DELETE CASCADE,
    relation    TEXT NOT NULL,
    target      TEXT NOT NULL REFERENCES entities(name) ON DELETE CASCADE,
    valid_from  TEXT,
    valid_until TEXT,
    episode_id  INTEGER REFERENCES episodes(id),
    confidence  REAL DEFAULT 1.0,
    UNIQUE (source, relation, target, valid_from)
);

CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target);
CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation);
"""


@dataclass
class Entity:
    name: str
    type: str
    description: str = ""


@dataclass
class Edge:
    source: str
    relation: str
    target: str
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    episode_id: Optional[int] = None
    confidence: float = 1.0

    def cite(self) -> str:
        """Render this edge as a citable line of graph evidence."""
        span = ""
        if self.valid_from or self.valid_until:
            span = f" [{self.valid_from or '?'} .. {self.valid_until or 'present'}]"
        ep = f" (episode {self.episode_id})" if self.episode_id else ""
        return f"{self.source} --{self.relation}--> {self.target}{span}{ep}"


class GraphStore:
    """A small temporal knowledge graph.

    Every write goes through here, which is what makes the validation gate
    in validate.py enforceable rather than advisory.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---------------------------------------------------------------- writes

    def add_episode(self, source: str, body: str, occurred_at: str | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO episodes (source, occurred_at, body) VALUES (?, ?, ?)",
            (source, occurred_at, body),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def upsert_entity(self, name: str, type: str, description: str = "") -> str:
        name = self.resolve(name)
        self.conn.execute(
            """INSERT INTO entities (name, type, description) VALUES (?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET
                 description = CASE
                   WHEN length(excluded.description) > length(entities.description)
                   THEN excluded.description ELSE entities.description END""",
            (name, type, description),
        )
        self.conn.commit()
        return name

    def add_alias(self, alias: str, canonical: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO aliases (alias, canonical) VALUES (?, ?)",
            (alias, canonical),
        )
        self.conn.commit()

    def resolve(self, name: str) -> str:
        """Map an alias to its canonical entity name."""
        row = self.conn.execute(
            "SELECT canonical FROM aliases WHERE alias = ?", (name,)
        ).fetchone()
        return row["canonical"] if row else name

    def add_edge(
        self,
        source: str,
        relation: str,
        target: str,
        valid_from: str | None = None,
        valid_until: str | None = None,
        episode_id: int | None = None,
        confidence: float = 1.0,
    ) -> bool:
        """Insert an edge. Returns False if it was a duplicate."""
        source, target = self.resolve(source), self.resolve(target)
        try:
            self.conn.execute(
                """INSERT INTO edges
                   (source, relation, target, valid_from, valid_until, episode_id, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (source, relation, target, valid_from, valid_until, episode_id, confidence),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def invalidate(self, source: str, relation: str, target: str, valid_until: str) -> int:
        """Close an open edge. This is how a graph learns that a fact expired."""
        cur = self.conn.execute(
            """UPDATE edges SET valid_until = ?
               WHERE source = ? AND relation = ? AND target = ? AND valid_until IS NULL""",
            (valid_until, self.resolve(source), relation, self.resolve(target)),
        )
        self.conn.commit()
        return cur.rowcount

    # ---------------------------------------------------------------- reads

    def entity(self, name: str) -> Optional[Entity]:
        row = self.conn.execute(
            "SELECT * FROM entities WHERE name = ?", (self.resolve(name),)
        ).fetchone()
        return Entity(row["name"], row["type"], row["description"]) if row else None

    def search_entities(self, term: str, limit: int = 10) -> list[Entity]:
        rows = self.conn.execute(
            """SELECT * FROM entities
               WHERE name LIKE ? OR description LIKE ?
               ORDER BY length(name) LIMIT ?""",
            (f"%{term}%", f"%{term}%", limit),
        ).fetchall()
        return [Entity(r["name"], r["type"], r["description"]) for r in rows]

    def edges_of(self, name: str, as_of: str | None = None) -> list[Edge]:
        name = self.resolve(name)
        rows = self.conn.execute(
            "SELECT * FROM edges WHERE source = ? OR target = ?", (name, name)
        ).fetchall()
        edges = [self._row_to_edge(r) for r in rows]
        return [e for e in edges if _valid_at(e, as_of)] if as_of else edges

    def subgraph(
        self, seeds: Iterable[str], hops: int = 1, as_of: str | None = None, max_edges: int = 60
    ) -> list[Edge]:
        """Retrieve the smallest useful neighbourhood around some seed entities.

        This is the function that keeps you from sending 50,000 nodes to a
        frontier model. Bounded by hops AND by max_edges, because one
        hub entity can blow up a 2-hop expansion on its own.
        """
        frontier = {self.resolve(s) for s in seeds}
        seen_nodes: set[str] = set()
        collected: dict[int, Edge] = {}

        for _ in range(max(hops, 0)):
            if not frontier or len(collected) >= max_edges:
                break
            nxt: set[str] = set()
            for node in frontier:
                if node in seen_nodes:
                    continue
                seen_nodes.add(node)
                rows = self.conn.execute(
                    "SELECT * FROM edges WHERE source = ? OR target = ?", (node, node)
                ).fetchall()
                for r in rows:
                    edge = self._row_to_edge(r)
                    if as_of and not _valid_at(edge, as_of):
                        continue
                    if len(collected) >= max_edges:
                        break
                    collected[r["id"]] = edge
                    nxt.add(edge.target if edge.source == node else edge.source)
            frontier = nxt - seen_nodes

        return list(collected.values())

    def episode(self, episode_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM episodes WHERE id = ?", (episode_id,)
        ).fetchone()

    def stats(self) -> dict:
        q = lambda s: self.conn.execute(s).fetchone()[0]  # noqa: E731
        return {
            "entities": q("SELECT count(*) FROM entities"),
            "edges": q("SELECT count(*) FROM edges"),
            "episodes": q("SELECT count(*) FROM episodes"),
            "open_edges": q("SELECT count(*) FROM edges WHERE valid_until IS NULL"),
            "aliases": q("SELECT count(*) FROM aliases"),
        }

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _row_to_edge(r: sqlite3.Row) -> Edge:
        return Edge(
            source=r["source"],
            relation=r["relation"],
            target=r["target"],
            valid_from=r["valid_from"],
            valid_until=r["valid_until"],
            episode_id=r["episode_id"],
            confidence=r["confidence"],
        )

    def close(self) -> None:
        self.conn.close()


def _valid_at(edge: Edge, as_of: str) -> bool:
    """Temporal filter. String comparison works because we use ISO-ish dates."""
    if edge.valid_from and as_of < edge.valid_from:
        return False
    if edge.valid_until and as_of >= edge.valid_until:
        return False
    return True


def render_context(edges: list[Edge], question: str = "") -> str:
    """Format a subgraph as the grounded context block you hand to a model."""
    lines = ["GRAPH EVIDENCE (answer only from these edges; say so if insufficient):"]
    for e in edges:
        lines.append(f"  - {e.cite()}")
    if question:
        lines += ["", f"QUESTION: {question}"]
    return "\n".join(lines)
