---
title: "Measure it, do not assume it"
order: 9
part: "Part 3 — Making it affordable"
summary: "The metrics that expose extraction quality, cache behavior, retrieval bounds, and real cost per episode."
minutes: 25
hands_on: true
---

Every number in your architecture that you did not measure is decoration. That includes the cache hit rate somebody assumes is high, the cost-per-episode estimate copied from a pricing page, the claim that extraction is accurate enough, and the claim that retrieval is selective.

This lesson gives those claims a measurement procedure. The goal is not a dashboard full of numbers. The goal is to discover which part of the pipeline is lying to you before it becomes expensive or permanent.

Why this matters more in an agentic graph than in a normal database: the agent's writes become its own future evidence. A gate that quietly stopped rejecting anything does not announce itself. It compounds, and by the time answers are visibly wrong you cannot tell which retrievals were poisoned.

## The metrics worth keeping

| Metric | Calculation | What it tells you |
|---|---|---|
| Cache hit rate | `cache_read / (cache_read + cache_write)` | Whether your supposedly stable prefix actually stays stable across requests. |
| Cost per episode | total input and output cost / episodes ingested | What it costs to add one episode, including the real model and request mix. |
| Extraction precision and recall | compare extracted facts with hand labels | Whether the extractor is adding wrong facts, missing real facts, or both. |
| Duplicate entity rate | entities that should have merged / entities inspected | Whether canonicalization and alias handling are fragmenting memory. |
| Edge rejection rate by reason | rejected candidates grouped by validation reason | Which schema or grounding failures the extractor produces. |
| Retrieval sufficiency | questions answerable from retrieved subgraphs / evaluated questions | Whether the evidence block is enough before a model starts reasoning. |
| Context economy | edges sent to the model / edges in the graph | Whether retrieval stays selective as the graph grows. |

Each metric has a different failure mode. Do not collapse them into one "quality" score. A cheap extractor can have a low cost per episode and terrible recall. A high cache hit rate can coexist with a bad relation vocabulary. A model can write elegant answers even when retrieval sufficiency is poor.

## Start with the cache you actually got

The cache hit rate is the first thing people assume and rarely inspect. In the lab, `ClaudeExtractor` records `input`, `output`, `cache_write`, and `cache_read` tokens from each response. Its method calculates exactly this:

```python
reads = sum(r["cache_read"] for r in self.usage_log)
writes = sum(r["cache_write"] for r in self.usage_log)
total = reads + writes
return reads / total if total else 0.0
```

That denominator is cache reads plus cache writes. It is not all input tokens. It answers a narrower question: of cache traffic, how much was served as a read rather than created as a write?

Track the rate by deployment, model, prompt version, and time window. A sudden drop usually means someone changed the stable prefix, altered its order, shortened its lifetime, or spread work across request shapes that do not share a cache. The corrective action is to inspect the actual serialized prefix, not to assume the cache provider is unreliable.

Cost per episode is similarly concrete:

```text
total model cost for the ingest run
-----------------------------------
number of episodes successfully ingested
```

Include input, cached reads, cache writes, and output at the provider's current rates. Decide and document whether failed calls and retries count. They should count in an operational budget because they appear on the invoice. Keep price data dated and sourced. A model price is not a timeless constant.

## Quality needs a hand-labeled sample

For extraction precision and recall, sample 50 episodes from the real distribution. Hand-label the entities and relationships you believe the system should extract. Then compare the extractor against that reference.

For any fact type, use:

```text
precision = correct extracted facts / all extracted facts
recall    = correct extracted facts / all hand-labeled facts
```

Define an exact matching rule before scoring. For example, an edge might match only when normalized source, relation, target, and expected time field match. Be explicit about whether a partial date is acceptable. Score entities and edges separately if you need to know whether errors come from recognition or relationship extraction.

There is no shortcut around hand-labeling. A model cannot fairly grade its own extraction without reproducing the same assumptions. A second model only moves the unmeasured judgment to another model. Fifty carefully labeled episodes is more useful than ten thousand unlabeled ones when you are deciding what to fix.

Duplicate entity rate is another manual-review metric at first. Inspect a sample of entities, identify groups that represent the same real thing but failed to merge, then record the proportion. The lab's `normalize_name()` collapses internal whitespace runs, strips surrounding whitespace and trailing punctuation, and strips common corporate suffixes, so "Apple  Inc." and "Apple" resolve to the same node. `GraphStore.add_alias()` and `GraphStore.resolve()` handle known aliases. Those are useful mechanisms, not evidence that your real corpus has no duplicate entities, and none of them is full entity resolution.

## Let the validation gate describe extractor failure

The validation result carries a `rejected` list of `(reason, item)` pairs. Its `.report()` method returns accepted entity and edge counts, then lists rejected items with their reasons. Group those reasons rather than reporting one flat rejection number.

A high rate of `relation '...' not in allowed vocabulary` says your extractor and schema disagree. `edge references undeclared entity` points to grounding failures. Invalid `valid_from` values point to temporal parsing. Each one suggests a different repair. Changing the model may not be the right first response.

<div class="callout"><strong>Rejected is not necessarily bad.</strong> A validation rejection means the gate worked. What matters is the rate, the reason mix, and whether the rejected fact was something you needed to preserve after correction.</div>

## Measure whether retrieval is doing its job

Retrieval sufficiency is a pre-reasoning test. Create a small set of real questions with expected facts. For each question, retrieve its subgraph and ask a human reviewer: could the answer be constructed from these edges alone? The fraction marked yes is the metric.

This separates retrieval failure from answer-writing failure. If the edge never reached the reasoning model, better prompting cannot recover it. If the required edge is present but the answer is wrong, the problem is in reasoning, citation use, or the answer contract.

Context economy is the complementary resource metric:

```text
context economy = edges sent to the model / edges in the graph
```

Low is normally good for a large graph, provided retrieval sufficiency stays high. A healthy large graph should send a small single-digit percentage of its edges for a typical question. Do not turn that into a target before measuring your own graph and question mix.

## The lab's real baseline

Run the dependency-free pipeline from the repository:

```bash
cd labs && .venv/bin/python -m graphlab.pipeline
```

Its verified output includes:

```text
Graph: {'entities': 8, 'edges': 9, 'episodes': 5, 'open_edges': 8, 'aliases': 2}
Rejected by the validation gate: 0
```

`GraphStore.stats()` is where those values come from. It returns counts for `entities`, `edges`, `episodes`, `open_edges`, and `aliases`. This is a baseline you can reproduce, not a benchmark for a production corpus.

The widest query in the same run also reports:

```text
Context economy: sent 9 of 9 edges (100% of the graph) for the widest query.
```

That 100 percent result is deliberate and useful. The graph has only nine edges, and a two-hop expansion from a well-connected node reaches all of them. It demonstrates hop explosion: a hop limit alone does not bound retrieval because one hub entity can expand a two-hop neighbourhood dramatically.

The store protects against this with both controls. Simplified, with annotations dropped for readability:

```python
def subgraph(self, seeds, hops=1, as_of=None, max_edges=60):
```

The actual declaration in `labs/graphlab/store.py` is fully annotated (`seeds: Iterable[str]`, `as_of: str | None`, returning `list[Edge]`). Read the file for the real thing rather than trusting a lesson's paraphrase, which is the habit this whole lesson is arguing for.

The implementation stops when its collected edges reach `max_edges`, and `graphlab/policy.py` clamps both `hops` and `max_edges` again at the MCP tool boundary, because arguments arriving from a model are untrusted input. Re-measure context economy as your graph grows. Do not take the tiny lab's 100 percent as an acceptable production result; a healthy large graph should send a small single-digit percentage.

## Hands-on: write a small measurement harness

Create `labs/measure.py` with the following script. It calls `ingest_episode`, the same ingestion boundary the pipeline and the MCP server use, so what you measure is what actually runs. It prints values computed from the run, groups rejections by their real reasons, and calculates the widest-query context ratio.

```python
from collections import Counter

from graphlab.extract import RegexExtractor
from graphlab.ingest import ingest_episode
from graphlab.sample_data import ALIASES, EPISODES, KNOWN_PEOPLE
from graphlab.store import GraphStore

store = GraphStore()
for alias, canonical in ALIASES.items():
    store.add_alias(alias, canonical)

extractor = RegexExtractor(known_people=KNOWN_PEOPLE)
rejections = Counter()

for episode in EPISODES:
    _, result, closed = ingest_episode(
        store,
        episode["body"],
        source=episode["source"],
        occurred_at=episode["occurred_at"],
        extractor=extractor,
    )
    print(result.report())
    rejections.update(reason for reason, _ in result.rejected)

stats = store.stats()
widest = store.subgraph(["Project Atlas"], hops=2, max_edges=20)
context_ratio = len(widest) / stats["edges"] if stats["edges"] else 0.0

print("stats:", stats)
print("rejections by reason:", dict(rejections))
print(f"context economy: {len(widest)}/{stats['edges']} ({context_ratio:.0%})")
```

Run it from `labs` with `.venv/bin/python measure.py`. Then extend it in two directions: feed it your hand-labeled 50-episode sample to score precision and recall, and, when using `ClaudeExtractor`, record its `usage_log` to calculate cache rate and dated cost per episode. Keep the raw samples and calculation rules with the results, or the number will become decoration again.

Next: the production track with Neo4j and Graphiti.
