---
title: "Extraction, and what it actually costs"
order: 4
part: "Part 2: Building the pipeline"
summary: "Why ingestion dominates graph-memory cost, and how cached prefixes, low effort, and batching change the bill."
minutes: 25
hands_on: true
sources:
  - anthropic-prompt-caching
---

Graph memory has one killer cost: every episode you ingest triggers extraction. Read the text, find entities, find relationships, attach time, validate it, then write the surviving facts to the graph. If an agent receives thousands of episodes, that work happens thousands of times.

Done naively at frontier-model rates, the memory layer can cost more than the application using it. The fix is not to ban good models. The fix is to stop spending frontier intelligence on mechanical work. Extraction is structured parsing. Traversal and multi-hop answers are where judgment earns the expensive model.

## The three levers

Apply these in order. The first changes the repeated-input shape, the second changes how much intelligence each call receives, and the third changes how non-urgent work is purchased.

### 1. Cache the stable prefix

The schema, relation vocabulary, and extraction rules should be byte-identical on every request. Put them first. Put the variable episode last.

That ordering is not style. It is the condition that makes prompt caching possible. If you interpolate a customer name into the instruction block, rebuild the schema per document, or make a tiny per-request "improvement" to the rules, you have changed the prefix. Your cache hit rate can fall to zero.

The lab puts this rule directly above its system prompt:

```python
# This string must be byte-identical across every request or your cache hit
# rate goes to zero. Do not template anything into it. Do not append the
# episode to it. Do not "improve" it per-document.
EXTRACTION_SYSTEM = """\
Extract a knowledge graph from the text.
...
"""
```

`EXTRACTION_SYSTEM` is the stable schema and rule block in `labs/graphlab/extract.py`. The real paid extractor passes that constant as a cached system block, then keeps the timestamp and episode in the user message:

```python
system=[
    {
        "type": "text",
        "text": EXTRACTION_SYSTEM,
        "cache_control": {"type": "ephemeral"},
    }
],
messages=[
    {
        "role": "user",
        "content": f"reference_time: {occurred_at}\n\n{episode_text}",
    }
],
```

The last line is variable by design. Do not move it into `EXTRACTION_SYSTEM`.

Anthropic prompt caching bills cached reads at a fraction of ordinary input. The provider's current pricing page is the source of truth for that fraction, cache writes, and expiry options. The system cannot infer a cache hit from having added `cache_control`, so `ClaudeExtractor` logs the usage fields it receives and measures it:

```python
def cache_hit_rate(self) -> float:
    """Measure it. Do not assume it."""
    reads = sum(r["cache_read"] for r in self.usage_log)
    writes = sum(r["cache_write"] for r in self.usage_log)
    total = reads + writes
    return reads / total if total else 0.0
```

A cache is an observed property of request traffic, not a checkbox in a design doc.

### 2. Do not use maximum reasoning for mechanical parsing

Deciding that `Google` is an organization is not a high-effort frontier reasoning task. The extraction prompt has a closed entity-type list, a closed relation vocabulary, explicit grounding rules, and JSON output. That is structured parsing with error handling.

Use a cheaper model and low effort for ingestion. Reserve expensive models and high effort for the query side, where the model must interpret the question, choose evidence, reason across multiple edges, handle time, and say when the evidence is insufficient.

The lab makes the cost-free version explicit. `RegexExtractor` is described as a "deterministic stand-in for an LLM extractor" and is the backend used by the core labs. It needs no API key, makes no model call, and is intentionally imperfect. Its job is to give you a reproducible pipeline before you buy inference.

<div class="callout"><strong>Cheap does not mean unguarded.</strong> A cheap extractor still sits behind the validation gate. Cost control never justifies letting an unverified entity or edge write directly to memory.</div>

### 3. Batch historical backfills

A historical import of 100,000 conversations is not an interactive request. Nobody is waiting for each episode while the import runs. Send non-time-sensitive extraction work through the Anthropic Batch API instead of paying the synchronous path for it.

Batch discounts and prompt caching address different parts of the work, so they can stack. Caching reduces the repeated stable prefix. Batching discounts eligible non-urgent requests, including their variable work under the provider's current terms. Keep fresh user-facing ingestion separate if it actually needs an immediate result.

## The minimum that decides whether any of this works

Before the arithmetic, the threshold that makes it real. Providers do not cache arbitrarily short prefixes. Anthropic's [documented minimum cacheable prompt length](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) is model-specific: 4,096 tokens for Claude Haiku 4.5 and Claude Opus 4.6/4.5, 1,024 for Opus 4.8 and the Sonnet 4.x/5 line, 512 for Opus 5. Below that, marking a block with `cache_control` does nothing at all. We checked that page on 2026-08-12; check it again before you budget, because these numbers move.

The failure is silent. From [the same page](https://platform.claude.com/docs/en/build-with-claude/prompt-caching): "Shorter prompts cannot be cached, even if marked with `cache_control`. Any requests to cache fewer than this number of tokens will be processed without caching, and no error is returned."

That matters for this lab. `EXTRACTION_SYSTEM` is about 920 characters, on the order of 200 tokens. Against `claude-haiku-4.5` and its 4,096-token minimum, **the lab's own prefix is far too short to cache**, and the API will not tell you. This is the honest state of the shipped code, not a hypothetical.

There are two defensible responses, and one indefensible one.

The indefensible one is padding the prefix with filler until it crosses 4,096 tokens. That buys a cache hit by inventing thousands of tokens of instructions you did not need, and you pay a cold cache write for all of them. You would be optimizing the metric instead of the bill.

The defensible responses:

1. **Accept that a small extraction prompt does not cache on a high-minimum model.** Keep the prefix tight, expect zero cache activity, and get your savings from the cheap model and batching instead.
2. **Pick a model whose minimum your genuine prefix can clear**, or genuinely need a large enough schema block. A detailed schema with entity type definitions, relation vocabulary, worked examples, and edge-case rules can legitimately exceed 1,024 tokens. If your prefix is that big because it needs to be, caching pays for itself.

Verify rather than assume. If both `cache_creation_input_tokens` and `cache_read_input_tokens` come back zero, nothing was cached, and the most common reason is missing the minimum.

## The arithmetic, as an illustration

Use this calculation to understand the shape of the optimization, not as a guaranteed invoice. Provider prices, cache policy, and model availability change. Before budgeting, plug current numbers from the provider's own pricing page into the placeholders below.

Assume 5,000 episodes, each with 800 variable tokens, against a model with a 1,024-token minimum and a genuine 1,200-token schema prefix that clears it:

| Component | Calculation | Input tokens |
|---|---:|---:|
| Variable episode text | 5,000 × 800 | 4,000,000 |
| Repeated stable prefix | 5,000 × 1,200 | 6,000,000 |
| Total at a flat input rate | 4M + 6M | 10,000,000 |

Let `P_input` be today's ordinary input cost per million tokens, `P_cached_read` be today's cached-read cost per million tokens, and `D_batch` be the applicable batch multiplier.

```text
Flat input cost
= 10 × P_input

Cached input shape, after cache warm-up
= 4 × P_input + 6 × P_cached_read

Cached and batch-eligible input shape
= D_batch × (4 × P_input + 6 × P_cached_read)
```

Those formulas exclude output and the initial cache write, which is billed at a premium over ordinary input. They also assume your requests actually arrive inside the cache lifetime: the default is five minutes, measured from the start of the request that writes the entry, and it refreshes on each hit. A backfill that trickles one episode every ten minutes caches nothing regardless of prefix size.

The important point is structural: with no cache, you repeatedly buy all 10 million input tokens at the ordinary rate. With a stable cached prefix that clears the minimum, the 6 million repeated tokens move to a cheaper class. Batching can reduce the non-urgent portion again.

Do not paste a stale dollar figure into an architecture review and call it a forecast. Record the model, date, provider price source, request mix, and measured usage alongside your calculation.

## Hands-on: run the free path first

The core lab uses `RegexExtractor`, so this command produces a graph without an API key and without a model bill:

```bash
cd labs && .venv/bin/python -m graphlab.pipeline
```

Watch the pipeline shape rather than the price. For each sample episode it adds the source episode, calls `extractor.extract(...)`, handles temporal closes, passes the payload through `commit(...)`, and only then makes graph writes. In a paid deployment, the cost would land at the extraction call. The episode write, SQLite graph write, and local validation are not model inference.

Then answer three questions in your notes:

1. Which text is identical across every extraction request? It is `EXTRACTION_SYSTEM`.
2. Which text must remain variable and last? `reference_time` plus `episode_text` in the user message.
3. Which corpus would be eligible for batch treatment: a live chat message, or last year's imported support archive?

If you later swap in `ClaudeExtractor`, preserve the exact prompt split first. Changing models cannot rescue a prefix you rebuild on every request.

Next: workflow graphs, where the pipeline becomes explicit and testable.
