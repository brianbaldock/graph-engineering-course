"""The validation gate.

The single most important file in this course. Bad data compounds in a
knowledge graph: one hallucinated edge becomes retrieved evidence, which
becomes a reasoned conclusion, which becomes another stored fact. This
module sits between the extractor and the graph write and refuses
anything it cannot justify.

Every rejection is returned with a reason so you can measure your
extractor rather than guess at it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

# Relations you actually expect. An open vocabulary is how a graph turns
# into mush: "works_at", "worked at", "employed_by", and "job" all become
# separate relations that never match at query time.
ALLOWED_RELATIONS = {
    "works_at",
    "worked_on",
    "involved",
    "depends_on",
    "owns",
    "located_in",
    "reports_to",
    "part_of",
    "uses",
    "authored",
    "caused",
    "replaced",
}

ALLOWED_TYPES = {"person", "organization", "project", "service", "technology", "place", "event"}

DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


def valid_date(value: str) -> bool:
    """Accept YYYY, YYYY-MM, or YYYY-MM-DD, and only real calendar dates.

    The regex alone is a shape check, not a date check: it happily
    accepts 2024-02-31 and 2024-99-99. A graph full of impossible dates
    still sorts and compares, it just answers temporal questions wrong,
    which is worse than failing loudly.
    """
    value = str(value)
    if not DATE_RE.match(value):
        return False
    parts = value.split("-")
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        date(year, month, day)
    except ValueError:
        return False
    return True


@dataclass
class ValidationResult:
    entities: list[dict] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)
    rejected: list[tuple[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.rejected

    def report(self) -> str:
        lines = [
            f"accepted: {len(self.entities)} entities, {len(self.edges)} edges",
            f"rejected: {len(self.rejected)}",
        ]
        for reason, item in self.rejected:
            lines.append(f"  ✗ {reason}: {item}")
        return "\n".join(lines)


def normalize_name(name: str) -> str:
    """Canonicalize an entity name.

    Collapse whitespace, strip trailing punctuation and common corporate
    suffixes so 'Apple Inc.' and 'Apple' don't become two nodes.
    """
    name = re.sub(r"\s+", " ", str(name)).strip().strip(".,;:")
    name = re.sub(r"\b(Inc|Inc\.|LLC|Ltd|Corp|Corporation|Co)\b\.?$", "", name).strip()
    return name


def normalize_relation(rel: str) -> str:
    return re.sub(r"[\s-]+", "_", str(rel).strip().lower())


def validate(payload: dict) -> ValidationResult:
    """Validate one extraction payload before it touches the graph.

    Expects the shape produced by the extraction schema:
        {"entities": [{name, type, description}],
         "edges":    [{source, target, relation, valid_from}]}
    """
    result = ValidationResult()

    if not isinstance(payload, dict):
        result.rejected.append(("payload is not an object", type(payload).__name__))
        return result

    # --- entities -------------------------------------------------------
    seen: dict[str, dict] = {}
    for raw in payload.get("entities") or []:
        if not isinstance(raw, dict) or "name" not in raw:
            result.rejected.append(("entity missing name", raw))
            continue
        name = normalize_name(raw.get("name", ""))
        etype = str(raw.get("type", "")).strip().lower()
        if not name:
            result.rejected.append(("entity name empty after normalization", raw))
            continue
        if etype not in ALLOWED_TYPES:
            result.rejected.append((f"entity type '{etype}' not in schema", name))
            continue
        if name in seen:
            # duplicate within one payload: keep the richer description
            if len(raw.get("description", "")) > len(seen[name]["description"]):
                seen[name]["description"] = raw.get("description", "")
            continue
        seen[name] = {"name": name, "type": etype, "description": raw.get("description", "")}

    result.entities = list(seen.values())
    known = set(seen)

    # --- edges ----------------------------------------------------------
    for raw in payload.get("edges") or []:
        if not isinstance(raw, dict):
            result.rejected.append(("edge is not an object", raw))
            continue
        src = normalize_name(raw.get("source", ""))
        tgt = normalize_name(raw.get("target", ""))
        rel = normalize_relation(raw.get("relation", ""))
        vf = raw.get("valid_from") or None

        if not src or not tgt:
            result.rejected.append(("edge missing source or target", raw))
            continue
        if src == tgt:
            result.rejected.append(("self-referential edge", f"{src} --{rel}--> {tgt}"))
            continue
        if rel not in ALLOWED_RELATIONS:
            result.rejected.append((f"relation '{rel}' not in allowed vocabulary", raw))
            continue
        # Grounding check: an edge may only reference entities the same
        # payload actually declared. This is what stops the model from
        # quietly inventing a participant.
        if src not in known or tgt not in known:
            missing = src if src not in known else tgt
            result.rejected.append((f"edge references undeclared entity '{missing}'", raw))
            continue
        if vf is not None and not valid_date(vf):
            result.rejected.append((f"valid_from '{vf}' is not a real YYYY[-MM[-DD]] date", raw))
            continue

        result.edges.append(
            {"source": src, "target": tgt, "relation": rel, "valid_from": vf}
        )

    return result


def commit(store, payload: dict, episode_id: int | None = None) -> ValidationResult:
    """Validate, then write only what survived. Returns the full result."""
    res = validate(payload)
    for e in res.entities:
        store.upsert_entity(e["name"], e["type"], e["description"])
    for edge in res.edges:
        store.add_edge(
            edge["source"],
            edge["relation"],
            edge["target"],
            valid_from=edge["valid_from"],
            episode_id=episode_id,
        )
    return res
