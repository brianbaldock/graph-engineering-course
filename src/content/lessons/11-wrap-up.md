---
title: "What you actually learned"
order: 11
part: "Part 4 — Production"
summary: "The transferable lesson, the mistakes worth remembering, and how to read the next viral architecture thread."
minutes: 15
hands_on: false
---

## The through-line

One sentence carried this entire course:

> Spend intelligence exactly where intelligence is needed.

Everything else was a consequence. Cache the stable prefix, because repeated identical context shouldn't cost full price. Batch the backfill, because nobody is waiting. Retrieve a subgraph, because reasoning over 50,000 nodes to answer a question about three is waste dressed as thoroughness. Validate before writing, because bad memory compounds. Keep timestamps, because a fact without a time is a fact you can't correct.

A naive agent treats every token the same. A good one knows:

| Signal | Response |
|---|---|
| Repeated context | Cache it |
| Historical workload | Batch it |
| Mechanical extraction | Cheap model, low effort |
| Multi-hop judgment | Frontier model, high effort |
| Large graph | Retrieve first, reason second |
| Time-sensitive fact | Preserve the timestamp |
| Model output | Validate before storage |

That's graph engineering. Not "put everything in Neo4j and call a frontier model."

## The bigger idea

The genuinely interesting shift isn't that some model got cheaper. It's that **model economics became an architecture problem.**

There was a period where the right move was to send everything to the best available model and let it sort things out. That worked because volumes were small and the bill was somebody's experiment budget. At production volume, undifferentiated frontier calls are the dominant line item, and the fix isn't a better prompt. It's an architecture that knows which work deserves which resource.

That is a systems design skill, and it's the durable part of what you learned here. Model names in this course will be stale within a year. The split between mechanical and judgment work will not be.

## The seven mistakes

Worth keeping somewhere you'll see them:

1. **Using the most expensive model for everything.** You don't need maximum intelligence to determine that "Sam joined OpenAI in 2025" contains a person, an organization, and a date.
2. **Forgetting prompt caching.** An identical 600-token schema across 5,000 requests is 3 million tokens of repeated context at full price for no reason.
3. **Sending the entire graph to the model.** Retrieval exists. Find the relevant subgraph, then reason.
4. **Treating every relationship as permanent.** People change jobs, services get replaced, dependencies disappear. A graph without time is wrong the moment the world moves.
5. **Letting unvalidated extraction write to production.** One hallucinated relationship contaminates every future answer that touches it.
6. **Processing historical data synchronously.** Backfills are the definition of a batch workload.
7. **Building only vector memory.** Vectors are excellent at similarity and are not a substitute for explicit relationships and temporal state.

## Reading the next thread

You'll see another architecture claim go viral within a month. Here's the audit that costs five minutes and saves five hours, applied to the one that started this course:

**Check the primary source.** The post said an Anthropic engineer demonstrated agentic graphs in a video. The top reply pointed out the video was the Claude Code release demo, not a graph lecture. One click.

**Check whether numbers are sourced.** "90% of our engineers" appeared as 70% in earlier variants of the same post, with the timeline shifting between "3-6 months" and "4-6 months" depending on who posted it. Numbers that drift between retellings are decoration.

**Run the config.** The article's MCP configuration referenced `uvx graphiti-mcp`. One curl against PyPI returns 404. The fabricated part was, predictably, the part that looked most copy-pasteable.

**Separate the claim from the architecture.** And this is the important one: the hype was inflated *and the underlying architecture was sound.* Extraction/traversal splitting, cached prefixes, temporal edges, validation gates, hybrid retrieval. All real, all worth learning. If you'd dismissed the whole thing because the framing was overheated, you'd have missed something useful.

That's the balance worth holding. Cynicism and credulity are both ways of not doing the work.

<div class="callout">
<strong>The claim that should have tipped you off.</strong> "No more prompting." Every node in an agentic graph is a prompt. Graph engineering doesn't eliminate prompting, it demotes prompting from being the whole job to being one component with a defined contract and a testable output. That's a real and valuable shift. It just isn't the one the headline promised.
</div>

## Where to take it

Ranked by how much you'll learn per hour:

1. **Point it at your own data.** Your git history, your notes, your team's decision docs. The sample corpus is a teaching aid. Your data has the messy entity resolution and genuine temporal ambiguity that make this interesting.
2. **Measure your real cache hit rate.** Almost nobody does, and it is the highest-leverage number in the whole system.
3. **Build the hybrid retrieval seam.** Lesson 2 described it, the labs use plain SQL substring matching, which does not tolerate typos. Add real embeddings and fuse the results properly.
4. **Compare against Graphiti.** You have a hand-built baseline, which means you can evaluate a library rather than adopt it on faith.
5. **Write the contradiction detector.** When a new episode conflicts with an existing edge, decide deliberately: update, close, or flag for a human. That decision is where most of the remaining hard problems live.

## What you have

Not a certificate. A repo you can run:

- A temporal knowledge graph with provenance on every edge
- A validation gate with 27 passing tests
- An extraction pipeline built for caching, with a free offline mode
- Bounded subgraph retrieval that cites its evidence
- An MCP server exposing it to Hermes and Copilot CLI, verified to load
- A routing policy that's a file rather than a slogan

And the habit of running the config before publishing it. That last one will outlast every model name in this course.
