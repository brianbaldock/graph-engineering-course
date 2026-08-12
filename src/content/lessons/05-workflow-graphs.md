---
title: "Agentic workflow graphs: prompts with contracts"
order: 5
part: "Part 2 — Building the pipeline"
summary: "Build a directed system of narrow, testable nodes instead of one giant prompt."
minutes: 25
hands_on: false
---

Lesson 0 gave “graph engineering” two meanings. The first is knowledge-graph memory: facts, relationships, and time stored as queryable structure. This lesson is about the other one: an **agentic workflow graph**, where the system's work is a directed graph of small nodes with explicit edges.

The two ideas work well together but are not interchangeable. A knowledge graph is durable state. A workflow graph is control flow. One tells an agent what it knows; the other determines what it does next.

## Stop making one prompt own the whole job

A mega-prompt usually asks one model to read an episode, find entities, propose facts, decide whether they are safe, write them, retrieve related evidence, and answer a question. It can look impressive in a demo. It is hard to test, expensive to tune, and difficult to repair when it fails.

A workflow graph splits that into nodes with a narrow job and named transitions:

```text
episode -> extract -> validate -> commit -> retrieve -> reason
                       |                  ^
                       +-> reject --------+
```

Each node has three things:

1. One narrow responsibility.
2. One model choice, or no model at all.
3. One output contract that the next node can check.

The course ingestion pipeline already has this shape: `episode -> extract -> validate -> commit -> (retrieve -> reason)`. It records an episode, produces candidate entities and edges, passes them through a validation gate, commits only accepted items, then retrieves a bounded subgraph for a model to reason over. The parentheses matter: retrieval and reasoning are usually a query-time branch, not work that must happen for every ingestion.

This does not mean “no more prompting.” That claim is false, as Lesson 0 established. Nodes that call a model are still prompts. The shift is that prompting stops being the entire application. It becomes one component with a defined input, a defined output, a cost, and a place where it may fail.

<div class="callout"><strong>The useful boundary.</strong> A prompt can propose a fact. It should not silently define the rules for accepting, storing, and retrieving that fact.</div>

## Why the graph beats the mega-prompt

The benefit is operational, not aesthetic.

| Property | One large prompt | Workflow graph |
|---|---|---|
| Testing | One broad behavior to inspect | Test a node against fixtures and its output contract |
| Model cost | One model price for every decision | Route mechanical work to a cheaper model and judgment to a stronger one |
| Failure handling | A weak answer can contaminate the whole run | Retry, reject, or route one failed node without replaying everything |
| Context | Accumulates every intermediate detail | Each node receives only its necessary inputs |
| Observability | One opaque transcript | Inputs, outputs, branch decisions, and latency per node |

If extraction is malformed, you test extraction. If an entity is unknown, the validation node rejects it. If a question lacks evidence, the reasoning node says so. Those are separate failures with separate fixes. You do not need to make a single instruction longer and hope it resolves all of them.

## The nodes and their edges

Workflow graphs need more than “call a model, then call another model.” Four common node types cover most pipelines.

### Transform

A transform converts one representation into another: episode text into candidate triples, triples into a retrieval request, or graph edges into a grounded context block. It might be deterministic Python, a model call, or both. Its contract should be concrete, such as JSON containing entity candidates and edges with `source`, `relation`, and `target`.

### Route or branch

A route selects a named outgoing edge from a rule or classification. The important word is explicit. “If validation fails, reject” must be visible in the graph and in code, not buried in a paragraph of an extraction prompt. A router might send an ambiguous item to human review, a supported item to commit, and an unsupported item to rejection.

### Validate or gate

A gate checks whether data may cross a boundary. It is the most important node in an ingestion graph. The extractor is allowed to be imperfect. The writer is not allowed to persist arbitrary output. A gate can enforce known entity types, allowed relations, required fields, source evidence, temporal consistency, or a confidence threshold. It should produce an accept or reject result with a reason.

The lab makes this architectural rather than advisory: graph writes pass through the validation and commit path. Its temporal-close handling is also a gate-shaped boundary. A statement that someone left an organization closes the open `works_at` edge before the remaining candidates are committed.

### Fan-out and reduce

Fan-out runs independent work in parallel, such as extracting entities, dates, and relations from the same episode, or retrieving neighborhoods for several resolved entities. A reduce node combines those outputs into one bounded result. Give the reducer a contract too, otherwise parallel work just moves the mega-prompt problem downstream.

A useful graph often mixes all four:

```text
                  -> extract people --\
episode -> fan-out -> extract relations -> reduce -> validate -> commit
                  -> extract dates ---/                   |
                                                        reject
```

The arrows are behavior. Conditional edges should carry conditions that can be tested: `valid -> commit`, `invalid -> reject`, `ambiguous -> review`. This makes retries safe. Retry a transient extraction failure, not a rejected fact. Re-run a reducer if one branch timed out, not the already committed write.

## Model routing with GitHub Copilot CLI

GitHub Copilot CLI is a useful driver because model selection is per invocation. For non-interactive, one-shot work, use this form:

```bash
copilot -p "<prompt>" --model <model> --allow-all-tools
```

`--allow-all-tools` is mandatory in `-p` mode. Without it, Copilot waits at its first permission prompt, which leaves a non-interactive workflow stuck. `--effort` sets reasoning depth; this CLI's parser accepts `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, and `max`, but **support is per model, not universal**. Some models reject the flag entirely, and asking for a level a model does not offer fails the call rather than degrading gracefully. Use `--plan` when you want read-only planning rather than changes.

Model names used in this course include `claude-haiku-4.5`, `claude-sonnet-4.6`, `claude-opus-4.8`, `gpt-5.5`, and `gpt-5.3-codex`. There is no `copilot models` subcommand, and asking a model to narrate its own availability is not verification. Use `auto` when you just need something to run:

```bash
copilot -p "list available models" --allow-all-tools --model auto
```

Availability can depend on your Copilot account, so discovery belongs in your local setup check.

Here is a small two-node shell sketch. The cheap node does extraction-shaped work. The expensive node makes the acceptance judgment. The output format is intentionally constrained so the second node receives a small, inspectable payload rather than the entire episode plus a pile of instructions.

```bash
#!/usr/bin/env bash
set -euo pipefail

# Create the paths this sketch writes to before running it.
mkdir -p episodes run
EPISODE_FILE="episodes/atlas-update.txt"
[ -f "$EPISODE_FILE" ] || echo "Project Atlas now uses Postgres 16." > "$EPISODE_FILE"
episode="$(<"$EPISODE_FILE")"

candidates="$({
  copilot -p "Extract candidate entities and relationship claims from this episode.
Return compact JSON only, with entities and edges. Do not write files.

EPISODE:
$episode" \
    --model claude-haiku-4.5 \
    --allow-all-tools
})"

judgment="$({
  copilot -p "Act as a validation gate. Evaluate these candidate graph claims.
Accept only claims supported by the supplied candidates, identify rejections with reasons,
and return compact JSON only. Do not write files.

CANDIDATES:
$candidates" \
    --model claude-opus-4.8 \
    --effort high \
    --allow-all-tools
})"

printf '%s\n' "$judgment" > run/validation-result.json
```

Note what is missing from the first call: there is no `--effort`. Reasoning effort is model-specific, and `claude-haiku-4.5` rejects the flag outright. A cheap model is cheap because it does less reasoning, so asking it for a reasoning level is a category error the CLI will refuse.

This is not a substitute for the repository's deterministic validation and commit code. It demonstrates routing. A real pipeline should parse the model output, validate its schema, then pass accepted items to the same gate that protects all writes. If node one returns invalid JSON, record the failure and retry or reject it. Do not pass untrusted prose straight to persistence because a stronger model liked it.

The two calls also expose an economic decision. Extraction has high volume and often mechanical rules, so `claude-haiku-4.5` is a plausible starting point. Judgment has lower volume and higher consequences, so `claude-opus-4.8` with high effort may be justified. Measure your actual error rate and cost before treating that split as policy.

## Parallel nodes and Hermes Agent

Independent fan-out branches do not need to wait on each other. In Hermes Agent, `delegate_task` is the equivalent control for assigning parallel independent node work to subagents. Use it where branches have separate inputs and their outputs can be reduced later. Keep dependent stages ordered: validation cannot run until extraction has produced a candidate, and commit cannot run until the gate has accepted it.

The goal is not to add nodes until the diagram is impressive. It is to place boundaries where they buy testability, cost control, or safety. Keep a node when you can name its contract and failure path. Merge nodes when they share the same model, context, and retry policy. The graph is a tool for making decisions explicit, not a ritual.

Next: the validation gate that decides what earns a permanent place in the graph.
