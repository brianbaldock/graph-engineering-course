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

import sys
from pathlib import Path


class PolicyError(RuntimeError):
    """Raised when a policy file exists but cannot be trusted.

    Used by strict callers (a server at startup) that would rather refuse
    to run than serve limits the operator did not write.
    """


DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "routing_policy.yaml"

# Used when the file is missing or PyYAML is not installed. The lab still
# has to bound retrieval, so these are conservative and explicit.
FALLBACK_CAPS = {"max_hops": 2, "max_edges": 60}


def load_policy(path: str | Path | None = None, strict: bool = False) -> dict:
    """Read the policy file.

    Resolved relative to this module, not the working directory, because
    an MCP server is launched by an agent from wherever that agent
    happens to be.

    An unreadable or malformed policy is NOT silently treated as "no
    policy". This file's entire job is to constrain an agent, so a typo
    in it must not quietly widen the caps. An operator who tightens
    max_edges to 10 and fat-fingers the YAML would otherwise get the
    default 60 back with no error and no log line, which is the opposite
    of what they asked for.

    Failures always warn on stderr. With strict=True they raise, which is
    what a long-running server should do at startup: refuse to boot
    rather than serve wider limits than the operator wrote.
    """
    p = Path(path) if path else DEFAULT_POLICY_PATH

    def _fail(reason: str) -> dict:
        msg = f"policy: {reason} ({p}). Falling back to built-in defaults."
        if strict:
            raise PolicyError(msg)
        print(f"WARNING: {msg}", file=sys.stderr)
        return {}

    try:
        import yaml
    except ImportError:
        return _fail("PyYAML is not installed, cannot read policy")
    try:
        with open(p, "r", encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh)
    except OSError as exc:
        return _fail(f"could not be read: {exc}")
    except Exception as exc:
        return _fail(f"is not valid YAML: {exc}")

    if loaded is None:
        return _fail("is empty")
    if not isinstance(loaded, dict):
        return _fail(f"must be a mapping, got {type(loaded).__name__}")
    return loaded


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
