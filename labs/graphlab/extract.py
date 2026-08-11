"""Extraction: text episode -> {entities, edges}.

Two backends, one interface:

  RegexExtractor  — deterministic, free, offline. Used by the core labs so
                    you can run everything without an API key and get the
                    same result every time.
  ClaudeExtractor — the real thing, with the cached stable prefix. Costs
                    money. Marked optional in the course.

The point of this file is the SHAPE, not the cleverness: a stable schema
prefix that never changes, and variable episode text appended last. That
ordering is what makes prompt caching possible at all.
"""

from __future__ import annotations

import json
import os
import re
from typing import Protocol

# ---------------------------------------------------------------------------
# THE STABLE PREFIX
# This string must be byte-identical across every request or your cache hit
# rate goes to zero. Do not template anything into it. Do not append the
# episode to it. Do not "improve" it per-document.
# ---------------------------------------------------------------------------
EXTRACTION_SYSTEM = """\
Extract a knowledge graph from the text.

Return JSON only, no prose, no code fences:

{
  "entities": [
    {"name": "...", "type": "...", "description": "..."}
  ],
  "edges": [
    {"source": "...", "target": "...", "relation": "...", "valid_from": "..."}
  ]
}

Allowed entity types:
person, organization, project, service, technology, place, event

Allowed relations:
works_at, worked_on, involved, depends_on, owns, located_in,
reports_to, part_of, uses, authored, caused, replaced

Rules:
- Use canonical entity names. Drop corporate suffixes (Inc, LLC, Ltd).
- Resolve aliases only when identity is unambiguous.
- Every edge endpoint MUST also appear in the entities array.
- Extract only relationships explicitly supported by the text.
- Add valid_from as YYYY, YYYY-MM, or YYYY-MM-DD when the text gives a date.
- Never invent relationships to make the graph look complete.
- Keep descriptions under 15 words.
"""


class Extractor(Protocol):
    def extract(self, episode_text: str, occurred_at: str | None = None) -> dict: ...


# ---------------------------------------------------------------------------
# Free / offline backend
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?P<a>[A-Z][\w.]*(?: [A-Z][\w.]*)*) joined (?P<b>[A-Z][\w.]*(?: [A-Z][\w.]*)*)"), "works_at"),
    (re.compile(r"(?P<a>[A-Z][\w.]*(?: [A-Z][\w.]*)*) works at (?P<b>[A-Z][\w.]*(?: [A-Z][\w.]*)*)"), "works_at"),
    (re.compile(r"(?P<a>[A-Z][\w.]*(?: [A-Z][\w.]*)*) left (?P<b>[A-Z][\w.]*(?: [A-Z][\w.]*)*)"), "__left__"),
    (re.compile(r"(?P<a>[A-Z][\w.]*(?: [A-Z][\w.]*)*) (?:led|worked on|started) (?P<b>[A-Z][\w.]*(?: [A-Z][\w.]*)*)"), "worked_on"),
    (re.compile(r"(?P<a>[A-Z][\w.]*(?: [A-Z][\w.]*)*) depends on (?P<b>[A-Z][\w.]*(?: [A-Z][\w.]*)*)"), "depends_on"),
    (re.compile(r"(?P<a>[A-Z][\w.]*(?: [A-Z][\w.]*)*) replaced (?P<b>[A-Z][\w.]*(?: [A-Z][\w.]*)*)"), "replaced"),
    (re.compile(r"(?P<a>[A-Z][\w.]*(?: [A-Z][\w.]*)*) uses (?P<b>[A-Z][\w.]*(?: [A-Z][\w.]*)*)"), "uses"),
]

_DATE = re.compile(r"\b(\d{4}(?:-\d{2})?)\b")

# Minimal type lexicon so the offline lab produces schema-valid types.
_TYPE_HINTS = {
    "project": "project",
    "service": "service",
    "platform": "service",
    "api": "service",
    "team": "organization",
    "corp": "organization",
    "inc": "organization",
}


class RegexExtractor:
    """Deterministic stand-in for an LLM extractor.

    It is intentionally imperfect. Lesson 6 asks you to measure its errors,
    which is the whole point: you cannot improve an extractor you have not
    measured, and a real LLM extractor fails in the same CATEGORIES.
    """

    def __init__(self, known_people: set[str] | None = None):
        self.known_people = known_people or set()

    def _type_of(self, name: str) -> str:
        low = name.lower()
        for hint, t in _TYPE_HINTS.items():
            if hint in low:
                return t
        if name in self.known_people:
            return "person"
        # Single capitalized token with no corporate hint: guess person.
        return "person" if len(name.split()) <= 2 and name not in self.known_people else "organization"

    def extract(self, episode_text: str, occurred_at: str | None = None) -> dict:
        entities: dict[str, dict] = {}
        edges: list[dict] = []
        date_match = _DATE.search(episode_text)
        vf = date_match.group(1) if date_match else (occurred_at[:7] if occurred_at else None)

        for sentence in re.split(r"[.\n]", episode_text):
            for pat, rel in _PATTERNS:
                m = pat.search(sentence)
                if not m:
                    continue
                a, b = m.group("a").strip(), m.group("b").strip()
                for n in (a, b):
                    entities.setdefault(n, {"name": n, "type": self._type_of(n), "description": ""})
                if rel == "__left__":
                    # "left" is a temporal signal, not a relation. Lesson 5.
                    edges.append({"source": a, "target": b, "relation": "works_at",
                                  "valid_from": None, "_close": vf})
                else:
                    edges.append({"source": a, "target": b, "relation": rel, "valid_from": vf})

        return {"entities": list(entities.values()), "edges": edges}


# ---------------------------------------------------------------------------
# Paid backend — the shape that matters
# ---------------------------------------------------------------------------


class ClaudeExtractor:
    """Real extraction with a cached stable prefix.

    Requires: pip install anthropic, and ANTHROPIC_API_KEY set.
    The cache_control block is what turns the repeated schema from
    full-price input into cheap cached-read input.
    """

    def __init__(self, model: str = "claude-haiku-4-5", max_tokens: int = 2000):
        import anthropic  # imported lazily so the free labs need no dependency

        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = model
        self.max_tokens = max_tokens
        self.usage_log: list[dict] = []

    def extract(self, episode_text: str, occurred_at: str | None = None) -> dict:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=[
                {
                    "type": "text",
                    "text": EXTRACTION_SYSTEM,          # stable, cached
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"reference_time: {occurred_at}\n\n{episode_text}",  # variable, last
                }
            ],
        )
        u = resp.usage
        self.usage_log.append(
            {
                "input": u.input_tokens,
                "output": u.output_tokens,
                "cache_write": getattr(u, "cache_creation_input_tokens", 0),
                "cache_read": getattr(u, "cache_read_input_tokens", 0),
            }
        )
        return _parse_json(resp.content[0].text)

    def cache_hit_rate(self) -> float:
        """Measure it. Do not assume it."""
        reads = sum(r["cache_read"] for r in self.usage_log)
        writes = sum(r["cache_write"] for r in self.usage_log)
        total = reads + writes
        return reads / total if total else 0.0


def _parse_json(text: str) -> dict:
    """Models emit code fences even when told not to. Handle it."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group(0)) if m else {"entities": [], "edges": []}
