---
title: "What this is, and what it isn't"
order: 0
part: "Part 0 — Orientation"
summary: "The honest version of the graph engineering pitch, minus the hype that got it trending."
minutes: 10
hands_on: false
---

You probably got here from a post that looked something like this:

> "Anthropic engineer: 90% of our engineers were using self-improving loops. Now everyone shifted to building agentic Graphs. No more prompting."

Let's deal with that first, because starting a course on a false premise is a bad way to learn anything.

## The hype, audited

That post went viral in several variants, with the engineer percentage swapped between 70% and 90%, the timeline between "3-6 months" and "4-6 months," and the attached video described as a graph lecture. The top reply pointed out the video was not about graphs. It was the Claude Code release demo.

So:

- **"No more prompting" is false.** Every node in an agentic graph is a prompt. Graph engineering doesn't remove prompting, it *demotes* it from the whole job to one component of a system. That's a real shift. It is not the abolition of prompting.
- **The percentages are unsourced.** No named engineer, no talk, no citation. Treat them as decoration.
- **The architecture underneath is real and worth learning.** That's what this course keeps.

<div class="callout">
<strong>Why lead with this?</strong> Because the single most valuable skill in this field right now is telling a real architectural shift from a repackaged one. If you can't audit the claim, you can't audit the system you build from it.
</div>

## What graph engineering actually means

Two distinct things travel under the same name. Both are in this course, and knowing which one someone means saves a lot of confusion.

**1. Knowledge graph memory.** Your agent stores facts as entities and relationships with timestamps instead of as a pile of text chunks. It can traverse from a thing to its related things, and answer questions about how the world changed over time. This is the substance of the good article that circulated alongside the hype.

**2. Agentic workflow graphs.** Your agent system is a directed graph of small, single-purpose steps with defined edges, rather than one giant prompt that tries to do everything. Each node is cheap and testable. Routing between them is explicit.

### So what is an "agentic graph"?

The phrase gets thrown around without a definition, which is part of why the hype travels so easily. Here is the one this course uses, and it is the reason both halves above are in the same course:

> An **agentic graph** is the pair: a workflow graph that decides what happens next, and a knowledge graph it reads from and writes to. Neither half is agentic on its own. A workflow graph with no memory is a pipeline that forgets. A knowledge graph with no workflow is a database nobody queries.

What makes it *agentic* is the loop. The agent retrieves from the graph, acts, and writes back what it learned, so the next decision is made against a graph its own earlier decisions shaped. That feedback is the whole thing. It is also why the rest of this course cares so much about validation and time: in a system that reads its own writes, one bad edge is not a bad row, it is a bad belief that gets retrieved and reinforced.

Concretely:

- The **workflow graph** is Lesson 5 (nodes and routing) and Lesson 7 (which node gets which model).
- The **knowledge graph** is Lessons 2, 3, and 6 (structure, time, and the gate that guards it).
- The **loop** is Lesson 8, where MCP lets a real agent read and write the graph on its own.

If you only build one half, you have something useful. You do not have an agentic graph.

They connect: workflow graphs are how you *build* the knowledge graph affordably, and knowledge graphs are what let workflow nodes share state without ballooning context.

## The one idea that carries the whole course

> Spend intelligence exactly where intelligence is needed.

A naive agent treats every token the same. It calls a frontier model at maximum reasoning to decide that "Google" is an organization, and also to answer "why did the architecture change after the March migration." Those are wildly different problems and you are paying the same rate for both.

Graph engineering is the discipline of splitting those apart:

| Work | Volume | Judgment needed | Configuration |
|---|---|---|---|
| Extraction (text → entities, edges) | Very high | Low, mechanical | Cheap model, low effort, cached prefix, batched |
| Traversal and reasoning (subgraph → answer) | Low | High, multi-hop | Frontier model, high effort, small precise context |

Everything else in this course is a consequence of that table.

## What you'll build

By the end you will have, running on your own machine:

- A working temporal knowledge graph with a validation gate in front of it, in plain Python on SQLite. No database server, no cloud account, no API key for the core labs.
- An extraction pipeline with a stable cached prefix and a cost-per-episode number you measured yourself.
- A retrieval layer that pulls the smallest relevant subgraph and cites the edges it used.
- A routing policy your agent follows, written as a config file rather than a wish.
- The same graph wired into **Hermes Agent** (via `mcp_servers` in config) and **GitHub Copilot CLI** (via `copilot mcp add`) as persistent memory.

## Why Hermes and Copilot CLI, not Claude Code

Not out of contrarianism. Three reasons:

1. **Copilot CLI is model-agnostic.** One binary and one subscription gives you Claude, GPT, and Codex models behind `--model`. Graph engineering is about routing work to the right-priced model, and Copilot CLI lets you demonstrate that inside a single tool.
2. **Hermes has a native MCP client and durable memory of its own.** It connects to MCP servers at startup, discovers tools, and exposes them in every conversation. Its own memory and skills layer makes the "graph memory versus agent memory" boundary visible rather than theoretical.
3. **The architecture is portable.** Nothing here is CLI-specific. If you use Claude Code, the same MCP config works.

## Prerequisites

- Python 3.10+ and comfort reading it
- A terminal, and either Hermes Agent or GitHub Copilot CLI (setup is on the next page)
- Docker only for the optional Neo4j production track
- No prior graph database experience

You do not need an Anthropic API key for the core labs. Lessons that cost money are marked, and each has a free local alternative.

<div class="callout">
<strong>A standing rule for this course.</strong> Every command shown here was run before it was published. Where a widely-circulated config was wrong, this course says so and gives the verified one. You'll hit the first example of that in Lesson 8.
</div>

## Who wrote this

This course was written by Brian Baldock with substantial assistance from Hermes, an AI agent, working together since May 2026, about eleven weeks at the time of writing. Hermes did research, wrote and ran the lab code, executed the verification, and drafted prose. Brian directed the work, reviewed it, and is responsible for what is published here. Code is MIT licensed, prose CC BY 4.0.

That disclosure matters more than usual. A course that spends its first page auditing an unsourced viral claim does not get to be quiet about how it was made.

It also sets an honest boundary on the word "we." These rules come from running a real agent deployment and getting things wrong first:

- **Validate before you write, and record why you rejected something.** Learned by shipping a health check gated on file modification time, which fired incorrectly because an unrelated write looked identical to the event it watched for. Modification time answers "did this change," not "did this run do its job."
- **Verify by artifact, never by status string.** Learned from scheduled jobs that reported success while doing no work. Lesson 8's verifier exists in its current shape because of that habit.
- **Close facts temporally instead of overwriting them.** Learned from designing a memory system where losing the previous state made questions about the past unanswerable.
- **Route cheap and expensive work to different models.** Learned from cost pressure, and from a CLI call that failed because reasoning-effort levels are not universal across models. That is why Lesson 7 no longer publishes an effort list as if it were portable.

The `graphlab` package is a minimal executable textbook for those rules. It is **not** the production memory system behind that collaboration, which is file-backed rather than a SQLite graph. Treating a teaching lab as a production architecture would be the exact fabrication this course rejects. The principles are load-bearing; the lab is how you run them yourself in five minutes without an API key.
