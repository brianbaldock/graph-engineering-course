---
title: "The routing policy: make the tradeoff executable"
order: 7
part: "Part 3 — Making it affordable"
summary: "A model-routing policy that separates cheap ingestion from expensive, evidence-bound traversal."
minutes: 20
hands_on: true
---

"Spend intelligence where intelligence is needed" is a useful idea and a useless implementation. Until it is a file your system loads, it is a slogan that disappears under deadline pressure.

This lesson's deliverable is `labs/routing_policy.yaml`. It defines the split between ingestion and traversal, the bounds on retrieval, the things the system must never do, and the measurements that are deliberately blank until you collect them.

## Read the policy, do not admire it

Here is the course policy as it exists in the lab:

```yaml
# Graph routing policy
#
# This file is the deliverable of Lesson 7. It is the thing that turns
# "spend intelligence where intelligence is needed" from a slogan into a
# configuration your system actually reads.
#
# Load it, don't admire it:
#     import yaml; POLICY = yaml.safe_load(open("routing_policy.yaml"))

ingestion:
  model: claude-haiku-4-5        # cheap: extraction is mechanical parsing
  effort: low
  cache_stable_prefix: true      # schema first, episode last, byte-identical
  batch_for_backfill: true       # historical data is never time-sensitive
  max_output_tokens: 2000
  rules:
    - Keep extraction instructions byte-identical across every request.
    - Never template variable data into the cached prefix.
    - Store timestamps whenever the source provides temporal information.
    - Validate every entity and edge before writing to the graph.
    - Reject edges whose endpoints were not declared in the same payload.

traversal:
  model: claude-opus-4-8         # expensive: multi-hop reasoning is judgment
  effort: high
  rules:
    - Resolve the user's entities before touching the graph.
    - Retrieve the smallest relevant subgraph; never the whole graph.
    - Apply temporal filters BEFORE reasoning, not after.
    - Prefer direct graph evidence over model assumptions.
    - Cite the specific edges used to construct the answer.
    - If the retrieved subgraph is insufficient, say so instead of guessing.

retrieval:
  default_hops: 1
  max_hops: 2
  max_edges: 60                  # hop limits alone do not bound a hub node
  hybrid: true                   # vector finds the neighbourhood, graph explains it

never:
  - Send the entire graph to the model.
  - Rebuild or reorder the extraction prefix between requests.
  - Run large historical backfills synchronously.
  - Ask the model to invent missing relationships.
  - Treat a vector similarity hit as a verified relationship.
  - Let unvalidated extraction write directly to production.

budget:
  # Fill these in from YOUR measured numbers in Lesson 9. Numbers you did
  # not measure are decoration.
  target_cost_per_episode_usd: null
  measured_cost_per_episode_usd: null
  measured_cache_hit_rate: null
```

The model identifiers in this file match the Anthropic-style names used by the extraction code. A provider adapter can translate those identifiers where its own CLI uses a different spelling. Do not silently substitute a premium traversal model into the ingestion path because it "seems safer." The policy is making an economic claim about job shape.

## What each section commits you to

**`ingestion`** treats extraction as high-volume structured parsing. It selects a cheap model at low effort, requires a byte-identical cached prefix, permits batching for old data, caps output at 2,000 tokens, and names the non-negotiable write controls. The final two rules map to the lab's validation gate: entities and edges are checked before the graph is written, and an edge cannot reference an entity the same payload did not declare.

**`traversal`** spends more where judgment matters. It uses an expensive model at high effort, but it gives that model a small, precise evidence set. The model must resolve entities, retrieve narrowly, filter time before it reasons, prefer graph evidence, cite the edges it uses, and state insufficiency instead of filling the gap with plausible prose.

**`retrieval`** makes the context bound explicit. One hop is the normal request, two is the maximum, and 60 is the hard edge ceiling. `hybrid: true` preserves the division from Lesson 2: vectors find a possible neighbourhood, while the graph supplies the relationships that can be treated as evidence.

**`budget`** has `null` values on purpose. A target or measured cost copied from somebody else's architecture is decoration. Lesson 9 supplies the procedure for your own numbers.

## The never list is part of the policy

A list of prohibitions looks boring until one of them prevents a graph from becoming unusable.

| Never do this | Why it matters |
|---|---|
| Send the entire graph to the model | Retrieval exists to produce the smallest relevant subgraph. Whole-graph context turns a graph into expensive unstructured text and makes answers harder to audit. |
| Rebuild or reorder the extraction prefix | Prompt caching depends on an identical prefix. Reordering it or templating data into it destroys the cache key. |
| Run large historical backfills synchronously | Old imports are not interactive work. Synchronous processing leaves the available batch discount unused. |
| Ask the model to invent missing relationships | An invented edge is later retrieved as if it were memory. That poisons the evidence chain. |
| Treat vector similarity as a verified relationship | Similar language is a retrieval clue, not proof that two entities are connected. |
| Let unvalidated extraction write to production | A model can emit invalid types, unknown relations, malformed dates, or undeclared endpoints. The gate is what stops bad output becoming durable memory. |

<div class="callout"><strong>Policy is not a prompt.</strong> Put rules in prompts where the model must follow them, but put limits in code where the system must follow them even when the model does not.</div>

## Enforce it at the call boundary

Loading YAML is the easy part. The important move is that every stage obtains its model and effort from the loaded policy, rather than accepting arbitrary values scattered through application code.

```python
from pathlib import Path

import yaml

POLICY = yaml.safe_load(Path("routing_policy.yaml").read_text())


def route(stage: str) -> tuple[str, str]:
    section = POLICY[stage]
    return section["model"], section["effort"]


ingestion_model, ingestion_effort = route("ingestion")
traversal_model, traversal_effort = route("traversal")

traversal_system = "\n".join(POLICY["traversal"]["rules"])
```

Use `ingestion_model` and `ingestion_effort` when the extractor makes a model call. Keep the cache shape from Lesson 4 in that same path. For historical work, make the scheduling code read `batch_for_backfill` rather than relying on an operator to remember it.

Use `traversal_model` and `traversal_effort` only after retrieval has bounded the subgraph. Insert `traversal_system` into the system prompt of the reasoning step along with the rendered graph evidence. The policy words become model instructions, while `default_hops`, `max_hops`, and `max_edges` stay programmatic inputs to retrieval.

Validation is enforced by calling the lab's `commit(store, payload, episode_id=...)`, not by hoping the extraction prompt obeys its own rule. `commit` validates first and writes only entities and edges that survived.

## Mapping the policy to Copilot CLI and Hermes

Copilot CLI provides the per-invocation controls. In print mode, `--allow-all-tools` is mandatory. A cheap ingestion-shaped call can use the current CLI model spelling and low effort:

```bash
copilot -p "Extract schema-valid entities and explicit relations from this episode." --model claude-haiku-4.5 --effort low --allow-all-tools
```

For a traversal-shaped request, choose an expensive model and high effort only after your application has retrieved a bounded evidence block:

```bash
copilot -p "Answer only from the supplied graph evidence. Cite the edges used, or say the evidence is insufficient." --model claude-opus-4.8 --effort high --allow-all-tools
```

The available effort levels are `low`, `medium`, `high`, and `xhigh`. Current model names include `claude-haiku-4.5`, `claude-sonnet-4.6`, `claude-opus-4.8`, and `gpt-5.5`. `--model` and `--effort` route the CLI call. They do not replace your code's cache construction, retrieval cap, batch queue, or validation gate.

Hermes has a persistent default model configuration, not a magic automatic routing rule. Keep the default under `model.provider` and `model.default` in Hermes configuration, then make a wrapper or delegated call read this policy when different stages need different choices. For example, a project that uses the Anthropic-side policy identifier can set its ingestion default with:

```bash
hermes config set model.provider anthropic
hermes config set model.default claude-haiku-4-5
```

Use `hermes config edit` when you want to inspect the resulting configuration. More importantly, do not confuse a global default with enforcement. The wrapper that loads `routing_policy.yaml` remains responsible for choosing traversal separately and for injecting traversal rules into the reasoning prompt.

## Hands-on

1. Open `labs/routing_policy.yaml` and compare it to the policy block above. Keep the budget fields null.
2. Add the `route()` helper to a scratch script and print the two tuples. You should see a low-effort ingestion route and a high-effort traversal route from one source of truth.
3. Run the free pipeline from `labs` and identify its two enforcement points: validation before graph writes, and bounded `subgraph(...)` retrieval before a model would reason.

```bash
cd labs && .venv/bin/python -m graphlab.pipeline
```

Next: wire the graph into Hermes and Copilot CLI as MCP memory.
