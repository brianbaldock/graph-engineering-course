---
title: "The temporal model: time is not metadata"
order: 3
part: "Part 1 — Foundations"
summary: "Put time on relationships, preserve expired facts, and answer questions about the world as it was."
minutes: 25
hands_on: true
sources:
  - sqlite-null-uniqueness
---

A normal knowledge graph stores a statement like this:

```text
Alice -> works_at -> Company X
```

That statement is wrong the moment Alice changes jobs. It does not become slightly stale, it asserts something false while looking perfectly valid to a query. Replacing it with `Alice -> works_at -> Company Y` fixes today's answer by destroying yesterday's.

A temporal graph treats time as part of the relationship itself. The edge records when it was valid in the world:

```text
Alice -> works_at -> Company X  [2024 .. 2026)
Alice -> works_at -> Company Y  [2026 .. present)
```

Now the graph can answer “Where did Alice work when Project Atlas started?” rather than merely “Where does Alice work?” That difference is why time belongs on the edge, not in a note on an entity or a timestamp attached to the database row.

## The fact has a lifespan

In this course, an `Edge` has `source`, `relation`, `target`, `valid_from`, `valid_until`, `episode_id`, and `confidence`. Its `cite()` method renders the edge with its time span and, when present, its source episode. The identity is still a triple, but the claim is a triple over an interval.

There are three useful shapes to recognize:

| Shape | Fields | Meaning |
|---|---|---|
| Timeless or unknown-start | `valid_from` and `valid_until` are `NULL` | The graph has no usable date for this assertion. It remains available, but cannot support a precise historical claim. |
| Open edge | `valid_until` is `NULL` | The graph believes the fact is currently true. It may have a known `valid_from`. |
| Closed edge | `valid_until` has a value | The fact expired at that boundary. It is retained as historical evidence, not deleted. |

An open edge is not a promise that the fact is eternally true. It is a statement about the store's present belief. If a later episode says Alice left Northwind, the old edge becomes closed. The database keeps it because the prior statement was true for a period, and because an agent should be able to show why it once answered that way.

<div class="callout"><strong>Do not overwrite history.</strong> A superseded edge is evidence with an end date. Deleting it loses both historical answers and the audit trail that connects a claim to its episode.</div>

## Closing is not creating another relationship

This is the subtle operation that keeps a temporal graph coherent. “Alice left Northwind” is not a new `left` relationship to store beside `works_at`. It is a signal to close the currently open employment edge:

```python
g.invalidate("Alice", "works_at", "Northwind", "2026-03")
```

`invalidate(source, relation, target, valid_until)` updates only matching edges whose `valid_until IS NULL`, then returns the number of rows closed. It is deliberately idempotent in the useful sense: a matching open edge produces `1`; calling it again produces `0` because that edge is already closed. The repository test verifies this exact behavior for `g.invalidate("A", "works_at", "B", "2024")`: the first call returns `1`, and the second returns `0`.

The ingestion pipeline handles temporal closes before its validation and commit steps. A close signal is removed from the candidate edge payload, then `invalidate()` is called. Ordinary accepted claims go on to the normal graph write. That split matters: treating a departure as an ordinary edge would leave the original `works_at` edge open and cause two contradictory answers to look current.

Adding a replacement job is separate:

```python
g.add_edge("Alice", "works_at", "Contoso", valid_from="2026-03")
```

`add_edge()` accepts optional `valid_from`, `valid_until`, `episode_id`, and `confidence`, and returns `False` if the edge would duplicate the store's unique `(source, relation, target, valid_from)` combination. A duplicate is not a reason to erase or mutate prior evidence.

Two of those fields are doing work worth naming. `episode_id` is the provenance pointer from Lesson 2: it is what lets `cite()` show which raw input asserted this edge, and it is the difference between an auditable claim and a bare assertion. `confidence` is a float the extractor sets and the validation gate in Lesson 6 thresholds on. Neither is decoration; an edge without provenance cannot be audited, and an edge without confidence cannot be filtered.

### The uniqueness constraint has a sharp edge

The obvious way to write that constraint is wrong, and it fails silently:

```sql
-- Looks right. Is not.
CREATE UNIQUE INDEX idx ON edges (source, relation, target, valid_from);
```

In SQL, `NULL` is not equal to `NULL`. Two rows with a NULL `valid_from` are not duplicates as far as a unique index is concerned, so an undated edge can be inserted over and over:

```
naive UNIQUE(...valid_from):     5 identical undated edges accepted
lab COALESCE(valid_from, ''):    1 identical undated edge accepted
```

Undated edges are exactly the ones you get most often, because plenty of source text asserts a fact without a date. A naive index means every re-ingestion of the same document silently multiplies them. Nothing errors. The graph just quietly accumulates five copies of the same belief, and any confidence or count you compute from it is now wrong.

The lab's schema closes it by indexing on a coalesced expression, so all undated edges collapse onto the same key:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_edges_identity
    ON edges (source, relation, target, COALESCE(valid_from, ''));
```

Verify it yourself. `add_edge` on the same undated fact five times returns `[True, False, False, False, False]`, and the store holds one edge.

## A query is always about a time

Both `g.edges_of(name, as_of=None)` and `g.subgraph(seeds, hops=1, as_of=None, max_edges=60)` can take an `as_of` point. With no `as_of`, they return edges regardless of whether they are historical. With it, the store applies this rule:

```python
if edge.valid_from and as_of < edge.valid_from:
    return False
if edge.valid_until and as_of >= edge.valid_until:
    return False
return True
```

The end boundary is exclusive. An edge ending at `2026` is valid before `2026`, but it is not valid at `2026`. That gives adjacent employment edges clean handoff semantics: an old edge can end at `2026`, and a new one can start at `2026`, without both being valid for the same point-in-time query.

The store compares ISO-ish strings such as `2024`, `2024-03`, and `2024-03-15`. Lexicographic comparison works for consistently formatted ISO dates, which is a good small-lab simplification. It has a sharp edge: mixed granularity can surprise you. For example, a year-only value and a month-level query are strings with different precision, not normalized timestamps. Production systems should establish a precision policy or use real date types before making legal, financial, or operational decisions from the result.

The same filter applies during neighborhood retrieval. `g.subgraph(["Alice"], hops=1, as_of="2024-06")` walks only edges valid at that point, bounded by both `hops` and `max_edges`. That is how a reasoning model receives the historical neighborhood it needs rather than a mixture of current and expired relationships.

## Hands-on: ask the graph two different years

Run this after importing `GraphStore` from `graphlab.store`. It is the tested temporal behavior in the lab:

```python
g = GraphStore()
g.upsert_entity("Alice", "person")
g.upsert_entity("X", "organization")
g.upsert_entity("Y", "organization")
g.add_edge("Alice", "works_at", "X", valid_from="2024", valid_until="2026")
g.add_edge("Alice", "works_at", "Y", valid_from="2026")

{e.target for e in g.edges_of("Alice", as_of="2025")}  # {'X'}
{e.target for e in g.edges_of("Alice", as_of="2027")}  # {'Y'}
```

Notice what did not happen. We did not update an `Alice` record with a single employer field. We stored two relationships and selected the one valid at the question's date. Inspect the returned edge directly when debugging an answer:

```python
edge = g.edges_of("Alice", as_of="2025")[0]
print(edge.source, edge.relation, edge.target)
print(edge.valid_from, edge.valid_until, edge.episode_id, edge.confidence)
print(edge.cite())
```

`edges_of()` includes relationships where the supplied name is either source or target. For a question that spans several entities, seed `subgraph()` instead and keep the retrieved set bounded. The graph's temporal model only helps if it is actually used at retrieval time.

## Valid time is only half the story

There are two different clocks a serious graph may need:

- **Valid time:** when the fact was true in the world. This is what `valid_from` and `valid_until` model here.
- **Transaction or observation time:** when the system learned, received, or recorded the fact.

Those together are bi-temporality. They answer different questions. “Where did Alice work in June 2025?” uses valid time. “What did our system believe on 2025-06-15?” requires observation time as well. This course's SQLite store models only valid time. That is a deliberate simplification, not an accidental claim of full auditability.

### Exercise: add the second clock

Extend the `edges` table with an `observed_at` column, carry it through `add_edge()` and the `Edge` dataclass, and choose a policy for corrections. Then add a query that constrains both valid time and observation time. You should be able to ask questions such as: “What did we believe on date D about where Alice worked in January?” That distinction is essential when late reports, corrections, and backfilled data matter.

Next: extracting those time-aware claims, and what extraction actually costs.
