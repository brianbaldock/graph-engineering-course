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
# This file is the deliverable of Lesson 7: the thing that turns "spend
# intelligence where intelligence is needed" from a slogan into a file.
#
# Be precise about what is enforced, because a policy file that claims
# more than it does is worse than no file at all.
#
#   ENFORCED BY THE LAB (graphlab/policy.py, applied in mcp_server.py):
#     retrieval.max_hops
#     retrieval.max_edges
#   Those two are clamped on every MCP retrieval call, because tool
#   arguments come from a model and are untrusted input.
#
#   OPERATOR POLICY (read by you, applied in your agent and your
#   system prompts): everything else in this file. The lab does not
#   secretly pick your model or batch your backfills.

ingestion:
  model: claude-haiku-4.5        # cheap: extraction is mechanical parsing
  effort: null                   # Haiku 4.5 rejects --effort. Not all models take it.
  cache_stable_prefix: true      # schema first, episode last, byte-identical
  batch_for_backfill: true       # historical backfill only, not fresh ingestion
  max_output_tokens: 2000
  rules:
    - Keep extraction instructions byte-identical across every request.
    - Never template variable data into the cached prefix.
    - Store timestamps whenever the source provides temporal information.
    - Validate every entity and edge before writing to the graph.
    - Reject edges whose endpoints were not declared in the same payload.

traversal:
  model: claude-opus-4.8         # expensive: multi-hop reasoning is judgment
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
  max_hops: 2                    # ENFORCED
  max_edges: 60                  # ENFORCED. Hop limits alone do not bound a hub node.
  hybrid: false                  # The lab has no vector index. See Lesson 10.

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

<div class="callout">
<strong>Enforced versus documented.</strong> Read the header again, because it is the honest part. This lab enforces exactly two keys: <code>retrieval.max_hops</code> and <code>retrieval.max_edges</code>, clamped in <code>graphlab/policy.py</code> and applied on every MCP retrieval call. Everything else is operator policy that you apply in your own agent. A file that says "the system reads this" while the system reads two fields of it is the same unverified confidence this course exists to reject. Know which of your policy is code and which is a note to yourself.
</div>

Note `hybrid: false`. The lab has no vector index, so claiming hybrid retrieval here would describe a control that does not exist. Lesson 10 covers what changes when you add one.

The model identifiers match the spellings the Copilot CLI accepts today. Do not silently substitute a premium traversal model into the ingestion path because it "seems safer." The policy is making an economic claim about job shape.

## What each section commits you to

**`ingestion`** treats extraction as high-volume structured parsing: a cheap model, a byte-identical cached prefix, batching permitted for old data, output capped at 2,000 tokens, and the non-negotiable write controls. The final two rules map to the lab's validation gate: entities and edges are checked before the graph is written, and an edge cannot reference an entity the same payload did not declare.

**`traversal`** spends more where judgment matters. It uses an expensive model at high effort, but gives that model a small, precise evidence set. The model must resolve entities, retrieve narrowly, filter time before it reasons, prefer graph evidence, cite the edges it uses, and state insufficiency instead of filling the gap with plausible prose.

**`retrieval`** makes the context bound explicit, and these are the two keys the lab enforces in code. One hop is the normal request, two is the maximum, 60 is the edge ceiling. `hybrid` is `false` because this lab has no vector index; Lesson 10 covers what changes when you add one.

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

Loading YAML is the easy part. The important move is that limits become code the model cannot talk its way around. The lab does this in `graphlab/policy.py`:

```python
def clamp(hops: int, max_edges: int, policy: dict | None = None) -> tuple[int, int]:
    """Clamp caller-supplied retrieval bounds to policy."""
    caps = retrieval_caps(policy)
    hops = max(1, min(int(hops), caps["max_hops"]))
    max_edges = max(1, min(int(max_edges), caps["max_edges"]))
    return hops, max_edges
```

`mcp_server.py` calls it on every retrieval, because a tool argument arrives from a model and is untrusted input:

```python
hops, max_edges = clamp(hops, max_edges, POLICY)
edges = store.subgraph(entities, hops=hops, as_of=as_of or None, max_edges=max_edges)
```

Model and effort are a different kind of key. Read them from the same file and pass them to whatever makes your model call:

```python
POLICY = load_policy()
ingestion_model = POLICY["ingestion"]["model"]
traversal_model = POLICY["traversal"]["model"]
traversal_system = "\n".join(POLICY["traversal"]["rules"])
```

Insert `traversal_system` into the system prompt of the reasoning step alongside the rendered graph evidence. The policy words become model instructions; the caps stay programmatic. Validation is enforced by calling `commit(store, payload, episode_id=...)`, not by hoping the extraction prompt obeys its own rule.

## Mapping the policy to Copilot CLI and Hermes

Copilot CLI provides the per-invocation controls. In print mode, `--allow-all-tools` is mandatory. A cheap ingestion-shaped call uses the current CLI model spelling:

```bash
copilot -p "Extract schema-valid entities and explicit relations from this episode." --model claude-haiku-4.5 --allow-all-tools
```

For a traversal-shaped request, choose an expensive model and high effort only after your application has retrieved a bounded evidence block:

```bash
copilot -p "Answer only from the supplied graph evidence. Cite the edges used, or say the evidence is insufficient." --model claude-opus-4.8 --effort high --allow-all-tools
```

Notice that the ingestion call passes no `--effort`. This CLI's parser accepts `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, and `max`, but support is per model rather than universal: `claude-haiku-4.5` rejects the flag, and a model that does not offer a level fails the call instead of quietly degrading. That is why `ingestion.effort` is `null` in the policy file. Check `copilot --help` on your own install, because this list moves.

`--model` and `--effort` route the CLI call. They do not replace your code's cache construction, retrieval cap, batch queue, or validation gate.

Hermes has a persistent default model configuration, not a magic automatic routing rule. Keep the default under `model.provider` and `model.default` in Hermes configuration, then make a wrapper or delegated call read this policy when different stages need different choices:

```bash
hermes config set model.provider anthropic
hermes config set model.default claude-haiku-4.5
```

Use `hermes config edit` when you want to inspect the resulting configuration. More importantly, do not confuse a global default with enforcement. The wrapper that loads `routing_policy.yaml` remains responsible for choosing traversal separately and for injecting traversal rules into the reasoning prompt.

## What happens when the policy file is broken

Worth stating plainly, because this is where policy files usually betray you. `load_policy` used to swallow every failure and return an empty dict, which meant the built-in fallback caps applied. That sounds harmless. It is not, and the reason is uncomfortable:

```
malformed YAML  -> {'max_hops': 2, 'max_edges': 60}
shipped policy  -> {'max_hops': 2, 'max_edges': 60}
```

The fallback happens to equal the shipped policy, so the failure is *invisible*. An operator who tightens `max_edges` to 10 and fat-fingers the YAML gets 60 back with no error and no log line. The one file whose entire job is to constrain an agent had a fail-open path that silently widened the limits its author had just narrowed.

The lab now warns on stderr for every failure mode (unparseable, empty, wrong shape, missing, PyYAML absent), and `load_policy(strict=True)` raises instead. `mcp_server.py` loads strictly, so a server whose job is bounding an agent refuses to boot rather than serve limits the operator did not write.

Apply the same rule to your own deployment. A config loader that treats "I could not read your rules" as "there are no rules" is worse than having no config file, because it produces false confidence.

<div class="callout">
<strong>The batching flag has an exception.</strong> <code>batch_for_backfill</code> covers historical import, where nothing is waiting on the result. It does not cover fresh ingestion, and it does not cover an urgent correction. If a fact in your graph is wrong and an agent is acting on it right now, that re-ingestion is time-sensitive: send it on the normal path and record why you took the exception. "Historical data" is a statement about the queue, not about the data's age.
</div>

## Hands-on

1. Open `labs/routing_policy.yaml` and read the header. Note which two keys are marked ENFORCED and which are operator policy. Keep the budget fields null.
2. Install the dependency the policy loader needs, then prove the clamp works:

```bash
cd labs
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests/test_graphlab.py -q -k policy
```

3. Run the free pipeline and identify its two enforcement points: validation before graph writes, and bounded `subgraph(...)` retrieval before a model would reason.

```bash
.venv/bin/python -m graphlab.pipeline
```

Next: wire the graph into Hermes and Copilot CLI as MCP memory.
