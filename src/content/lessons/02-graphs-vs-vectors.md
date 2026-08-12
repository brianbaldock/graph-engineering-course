---
title: "Graphs versus vectors, and why the answer is both"
order: 2
part: "Part 1 — Foundations"
summary: "Similarity is not structure. What each store is actually good at, and where the hybrid seam goes."
minutes: 20
hands_on: false
---

A vector database gives an agent **semantic similarity**. A knowledge graph gives it **structure**. These are not competing answers to one question, they are answers to two different questions, and most agent memory failures come from asking one to do the other's job.

## The same fact, two ways

Store this in a vector database:

> "Alice worked on Project Atlas."

You get an embedding. Ask "what did Alice work on" and you'll get that chunk back, because the question is semantically near the text. Good.

Now ask: *which systems transitively depend on the thing Alice worked on?*

The vector store cannot answer this. Not because it's badly configured, but because the relationship "depends_on" was never stored as a traversable thing. It was stored as prose that happens to sit near other prose. There is no edge to walk.

The graph stores the same fact as structure:

```
Alice
  └── worked_on ──> Project Atlas
                      ├── started_at ──> 2024
                      ├── involved   ──> Bob
                      └── depends_on ──> Billing Service
                                           └── depends_on ──> Postgres
```

Now the traversal is mechanical. Two hops from Alice and you have Postgres, along with the path that justifies it.

## What structure buys you

Questions a graph answers natively and a vector store fundamentally cannot:

- **Multi-hop:** "Which systems depend on the thing Alice built?" Requires walking edges, not matching text.
- **Temporal:** "Where did Alice work when Atlas started?" Requires facts that know when they were true.
- **Aggregation over relationships:** "Who has worked on more than three projects?" Requires counting edges.
- **Causal chains:** "What decisions led to the current architecture?" Requires ordered, connected events.
- **Recorded absence:** "What does Atlas *not* depend on?" A structure can tell you it has **no recorded** dependency, which is a different and weaker claim than "no dependency exists." Absence of an edge is absence of evidence unless you separately commit to a closed-world assumption or store explicit negative facts. An open text corpus cannot even give you the weaker answer.

## What vectors do better

Be fair to the other side. Vectors win on:

- **Fuzzy entry.** The user says "the billing thing that broke last spring." No canonical entity name, no exact match. Embeddings find the neighbourhood; graph traversal takes it from there.
- **Unstructured nuance.** The *reasoning* inside a design doc rarely reduces to triples without losing the argument.
- **Cost.** Embedding is orders of magnitude cheaper than LLM extraction. A graph costs real money to build (Lesson 4).
- **Recall over precision.** When you don't know what you're looking for, similarity beats a schema that may not have anticipated the question.

## The hybrid seam

The productive architecture uses both, with a clear division of labour:

```
                 User Question
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
   Vector Search                 Graph Search
   "what's nearby?"             "how is it connected?"
        │                             │
   Semantic Context              Relationships + time
        └──────────────┬──────────────┘
                       ▼
                 Context Fusion
                       ▼
              Frontier model reasons
                       ▼
                Grounded Answer
```

Read it as a sentence: **vector retrieval finds the neighbourhood, graph traversal explains the structure, the frontier model synthesizes.**

In practice the seam is usually *entity resolution*. The user's loose phrase goes to the vector store (or plain substring search, which is what this course's labs use to stay dependency-free). That yields candidate entity names. Those names seed the graph traversal. You'll see exactly this in `mcp_server.py`, where `search_entities` must be called before `get_subgraph`.

Be precise about what the lab's version does and does not do. `search_entities` runs SQL `LIKE %term%` against entity names and descriptions. That matches substrings, so "Atlas" finds "Project Atlas". It does **not** tolerate typos: "Altas" finds nothing. Real fuzzy matching (edit distance) and semantic matching (embeddings) both belong here in production, and the lab has neither. This is the seam where you would add them.

## The rule that prevents the worst bug

<div class="callout">
<strong>Never treat a vector similarity hit as a verified relationship.</strong> Two chunks being semantically close means they use similar language. It does not mean the entities in them are related. Promoting similarity to a graph edge is how you poison a knowledge graph, and it is a surprisingly common shortcut.
</div>

A graph edge is evidence: someone asserted it, and you can point at the episode that did. A model-generated assumption is not evidence, no matter how confident the prose around it sounds. Lesson 6 builds the gate that enforces this distinction.

Two terms the rest of the course leans on, defined here so they are not doing silent work later:

- An **episode** is one raw input the graph learned from: a document, a message, a commit, a meeting note. It is stored whole, with its own timestamp, and it never gets rewritten. Edges point back to the episode that produced them.
- **Provenance** is that pointer. It is the difference between "the graph says Alice works at Northwind" and "this specific sentence, from this document, dated March 2024, says so." Provenance is what lets you audit a wrong answer instead of just regretting it.

The reason both matter more in a graph than in a document store: a chunk of text carries its own context with it, but an edge is a bare assertion. Strip the provenance off an edge and you have a claim with no way to check it, which an agent will then retrieve and act on with full confidence.

## When you don't need a graph

Honest counterweight, because this course would be worse without it. Skip the graph if:

- Your agent answers one-shot questions over a static corpus. That's RAG, and RAG is fine.
- You have fewer than a few hundred facts. A well-written text file in context beats any infrastructure.
- Your data has no meaningful relationships. A pile of independent support articles has no useful edges.
- Nothing ever changes. Temporal reasoning is a large share of the graph's value, and if your facts are immutable you've given up most of the return.

Graphs earn their cost when relationships and time matter, at a volume that won't fit in a context window. That's the case this course targets.

Next: the temporal model, which is the part most implementations skip and then regret.
