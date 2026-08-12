"""Load the routing policy and enforce the parts the lab can actually enforce.

Be careful about what this module claims. A policy file is only real to
the extent that code reads it and something changes as a result. The lab
enforces exactly two things, the retrieval caps, because those are the
two the lab has the machinery to enforce at a tool boundary:

    retrieval.max_hops
    retrieval.max_edges

Everything else in routing_policy.yaml (model choice, effort, batching,
cache shape, the never list, budgets) is operator policy for the agent
you wire this into. It is documentation for humans and for the system
prompt of your reasoning step, not something this 200-line lab silently
applies. Saying otherwise would make the file decorative in exactly the
way Lesson 9 warns about.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "routing_policy.yaml"

# Used when the file is missing or PyYAML is not installed. The lab still
# has to bound retrieval, so these are conservative and explicit.
FALLBACK_CAPS = {"max_hops": 2, "max_edges": 60}


def load_policy(path: str | Path | None = None) -> dict:
    """Read the policy file. Returns {} if it cannot be read.

    Resolved relative to this module, not the working directory, because
    an MCP server is launched by an agent from wherever that agent
    happens to be.
    """
    p = Path(path) if path else DEFAULT_POLICY_PATH
    try:
        import yaml
    except ImportError:
        return {}
    try:
        with open(p, "r", encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh)
    except (OSError, Exception):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def retrieval_caps(policy: dict | None = None) -> dict:
    """The two caps the lab enforces, validated into sane integers."""
    policy = policy if policy is not None else load_policy()
    section = policy.get("retrieval") or {}
    caps = dict(FALLBACK_CAPS)
    for key in ("max_hops", "max_edges"):
        value = section.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and value > 0:
            caps[key] = value
    return caps


def clamp(hops: int, max_edges: int, policy: dict | None = None) -> tuple[int, int]:
    """Clamp caller-supplied retrieval bounds to policy.

    An MCP tool argument is untrusted input: it arrives from a model.
    Negative, zero, and absurdly large values all get bounded here rather
    than deeper in the store.
    """
    caps = retrieval_caps(policy)
    try:
        hops = int(hops)
    except (TypeError, ValueError):
        hops = 1
    try:
        max_edges = int(max_edges)
    except (TypeError, ValueError):
        max_edges = caps["max_edges"]
    hops = max(1, min(hops, caps["max_hops"]))
    max_edges = max(1, min(max_edges, caps["max_edges"]))
    return hops, max_edges
