---
title: "The validation gate: stopping bad data before it compounds"
order: 6
part: "Part 2 — Building the pipeline"
summary: "A knowledge graph has a nasty property. Bad data doesn't just sit there, it reproduces."
minutes: 30
hands_on: true
---

If you only implement one thing from this course, implement this.

## Why this is the agentic part

It would be easy to read this lesson as database hygiene. It isn't. Validation only becomes urgent once the agent is writing to the graph on its own, which is the loop Lesson 0 defined: retrieve, act, write back, retrieve again.

A human-curated graph gets bad rows. An agentic graph gets bad *beliefs*, because the thing that wrote the edge is the same thing that will later retrieve it and treat it as established fact. Nobody is between the write and the next read. That is the whole reason the gate has to live in code rather than in a prompt asking the model to be careful.

## Why a bad edge is worse than a bad chunk

In a vector store, a bad chunk is inert. It surfaces occasionally, the model reads it, maybe it produces a wrong answer once. The damage is bounded by that single retrieval.

In a knowledge graph, a bad edge is generative:

```
Bad extraction
      ↓
Bad graph edge
      ↓
Bad retrieval          ← now it looks like verified evidence
      ↓
Bad reasoning          ← the model trusts it, because you told it to
      ↓
Bad memory written back
      ↓
More bad retrieval     ← and now it has friends
```

The loop closes. You built a system whose explicit purpose is to treat stored edges as ground truth, then you let unverified model output write to it. Every downstream component is faithfully doing its job while amplifying a mistake.

This is why ingestion is a **data pipeline problem**, not an LLM call. The LLM is one stage. The stages around it are what make the output trustworthy.

## The gate

The rule is simple: nothing reaches the graph without passing a validator that can explain its rejections.

```
LLM Extraction
      ↓
JSON schema validation      ← is it even the right shape?
      ↓
Entity normalization        ← "Apple Inc." and "Apple" are one node
      ↓
Duplicate detection
      ↓
Relationship validation     ← is this relation in my vocabulary?
      ↓
Grounding check             ← are both endpoints declared?
      ↓
Temporal validation         ← is that actually a date?
      ↓
Graph write
```

Open `labs/graphlab/validate.py`. It implements exactly that, in about 150 lines of plain Python. Here are the checks that matter most, and why.

### 1. A closed relation vocabulary

```python
ALLOWED_RELATIONS = {
    "works_at", "worked_on", "involved", "depends_on", "owns",
    "located_in", "reports_to", "part_of", "uses", "authored",
    "caused", "replaced",
}
```

An open vocabulary is how a graph turns to mush. Let the model choose freely and you will end up with `works_at`, `worked at`, `employed_by`, `employment`, and `job` as five distinct relations describing one thing. None of them match at query time. Your graph looks full and answers nothing.

Twelve relations is not a limitation, it is a schema. If you genuinely need a thirteenth, add it deliberately and re-extract.

### 2. Normalization before comparison

```python
def normalize_name(name: str) -> str:
    name = re.sub(r"\s+", " ", str(name)).strip().strip(".,;:")
    name = re.sub(r"\b(Inc|Inc\.|LLC|Ltd|Corp|Corporation|Co)\b\.?$", "", name).strip()
    return name
```

`normalize_name("Apple Inc.")` returns `"Apple"`. Without this, entity duplication kills you quietly: the graph has both nodes, each holds half the edges, and every query returns half an answer while looking perfectly healthy.

<div class="callout">
<strong>Entity resolution is a data problem, not a prompting problem.</strong> The instinct is to write a better prompt begging the model to be consistent. It will be inconsistent anyway, because it sees one episode at a time and has no view of what's already in your graph. Normalize deterministically in code, and keep an explicit alias table for the cases code can't infer.
</div>

### 3. The grounding check

This is the most important check in the file and the one people skip:

```python
# Grounding check: an edge may only reference entities the same
# payload actually declared. This is what stops the model from
# quietly inventing a participant.
if src not in known or tgt not in known:
    missing = src if src not in known else tgt
    result.rejected.append((f"edge references undeclared entity '{missing}'", raw))
    continue
```

Extraction hallucinations rarely look like nonsense. They look like a plausible extra participant appearing in the `edges` array who was never named in the `entities` array, because the model pattern-matched to what such a document usually contains. Requiring both endpoints to be independently declared in the same payload catches a large share of that for free.

### 4. Reject, but record why

```python
@dataclass
class ValidationResult:
    entities: list[dict]
    edges: list[dict]
    rejected: list[tuple[str, Any]]
```

Every rejection carries a reason. This is not politeness, it's instrumentation. A rejection log grouped by reason tells you precisely what your extractor is bad at:

- Lots of `relation not in allowed vocabulary`? Your prompt's relation list is drifting from your schema.
- Lots of `undeclared entity`? Your model is hallucinating participants, or your prompt isn't clear that endpoints must be declared.
- Lots of `not YYYY`? Your date instruction is too vague.

Without reasons you have a number. With reasons you have a work queue. Lesson 9 turns this into a metric.

## Hands-on

Run the test suite:

```bash
cd labs && .venv/bin/python -m pytest tests/ -q
```

```
......................                                                   [100%]
25 passed in 0.16s
```

Now read the tests that describe the gate. This one is the hallucination trap:

```python
def test_gate_rejects_ungrounded_edge():
    res = validate({
        "entities": [{"name": "A", "type": "person"}],
        "edges": [{"source": "A", "target": "Ghost Corp", "relation": "works_at"}],
    })
    assert res.edges == []
    assert any("undeclared entity" in r for r, _ in res.rejected)
```

`Ghost Corp` never appears in the entities array. It is exactly the shape of a confident hallucination, and the gate drops it while keeping the rest of the payload.

Note what the gate does *not* do: it doesn't throw away the whole extraction because one edge was bad. It accepts what survives and reports what didn't:

```python
def test_commit_writes_only_valid_rows():
    g = GraphStore()
    res = commit(g, {
        "entities": [{"name": "A", "type": "person"}, {"name": "B", "type": "organization"}],
        "edges": [
            {"source": "A", "target": "B", "relation": "works_at"},   # good
            {"source": "A", "target": "Nope", "relation": "works_at"}, # ungrounded
        ],
    })
    assert g.stats()["edges"] == 1
    assert len(res.rejected) == 1
```

Partial acceptance is the right default. All-or-nothing rejection throws away good facts because of one bad neighbour, and in a large backfill that silently costs you most of your graph.

## Exercises

1. **Break it on purpose.** Add an edge with `relation: "vibes_with"` and confirm the rejection reason names the relation. Then add it to `ALLOWED_RELATIONS` and watch it pass. Feel how deliberate a schema change should be.

2. **Add a confidence floor.** The `Edge` dataclass already carries `confidence`. Make the gate reject edges below a configurable threshold, and have `ClaudeExtractor` populate it. Then measure how many real edges you lose at 0.9 versus 0.7. There is a real precision/recall trade here and you should see it with your own numbers.

3. **Add contradiction detection.** If the graph already has an open `works_at` edge for a person and a new episode asserts a different employer with a later `valid_from`, that's a job change, not a conflict: close the old edge instead of writing a parallel one. Currently `pipeline.py` only handles this when the text literally says "left". Make it infer the close.

4. **Log rejections to a table.** Persist every rejection with its reason and episode id. That table is the input to Lesson 9's rejection-rate-by-reason metric.

<div class="callout">
<strong>The one-sentence version.</strong> A graph edge is evidence, and a model-generated assumption is not. The gate is where you enforce the difference, and it is the only place you can.
</div>

Next: the routing policy that decides which model does which half of the work.
