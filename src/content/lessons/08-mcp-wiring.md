---
title: "Wiring the graph into Hermes and Copilot CLI"
order: 8
part: "Part 3 — Making it affordable"
summary: "Expose your graph over MCP so your agent has memory that survives the session. Includes a config from the viral article that does not work."
minutes: 30
hands_on: true
---

Your graph is useless if only your scripts can reach it. This lesson puts it behind an MCP server and wires it into both drivers, so the agent can retrieve memory on demand instead of stuffing the whole history into its context window.

## First, a correction

The widely-shared article this course is built around gives this MCP configuration:

```json
{
  "mcpServers": {
    "graphiti": {
      "command": "uvx",
      "args": ["graphiti-mcp"],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_PASSWORD": "${NEO4J_PASSWORD}"
      }
    }
  }
}
```

That does not work. There is no `graphiti-mcp` package on PyPI:

```bash
$ curl -s -o /dev/null -w "%{http_code}\n" https://pypi.org/pypi/graphiti-mcp/json
404
```

`graphiti-core` exists as a library. The MCP server is not a published package, it lives in the `mcp_server/` directory of the getzep/graphiti repository and you run it from a checkout. The verified configuration is in Lesson 11.

<div class="callout">
<strong>Why this matters more than the typo.</strong> The article was otherwise substantially correct about the architecture. The config was the one part that looks most like a working artifact and is easiest to copy without testing, so it is the part that wasted the most reader time. Run the config before you publish it. That is the whole lesson.
</div>

## The server

`labs/mcp_server.py` exposes the course graph over MCP. The design choice worth noticing is what it does *not* expose.

There is no `run_query` tool. There is no `execute_cypher`. The four tools are exactly the operations the routing policy sanctions:

| Tool | Purpose |
|---|---|
| `search_entities` | Resolve a fuzzy phrase to canonical entity names. Call this first. |
| `get_subgraph` | Retrieve a bounded neighbourhood, optionally as of a date. |
| `add_knowledge` | Write an episode through the validation gate. |
| `graph_stats` | Report size and shape. |

**An MCP server is a policy surface, not just an API wrapper.** If you expose arbitrary query execution, your carefully written routing policy becomes a suggestion the model can route around. If the only retrieval tool is bounded by `hops` and `max_edges`, the model cannot send you the whole graph even if it wants to.

Notice the tool docstrings do real work:

```python
@mcp.tool()
def get_subgraph(entities: list[str], hops: int = 1, as_of: str = "", max_edges: int = 60) -> str:
    """Retrieve the smallest relevant subgraph around some entities.

    entities: canonical names from search_entities
    hops:     1 for direct relationships, 2 for transitive. Never more.
    as_of:    optional YYYY[-MM[-DD]] to see the graph as it was then.
    """
    edges = store.subgraph(entities, hops=min(hops, 2), as_of=as_of or None, max_edges=max_edges)
    if not edges:
        return "No edges found. Do not invent relationships; report the gap."
    return render_context(edges)
```

The docstring is the model's instruction manual, so it says "call `search_entities` first" and "never more than 2 hops." And the empty case returns an explicit instruction rather than an empty string, because an empty result is precisely when a model is most tempted to fill the silence from its training data.

The `min(hops, 2)` is the belt to that suspenders. Instructions guide, code enforces.

## SDK version gotcha

MCP SDK 2.0 renamed the server class. `mcp.server.fastmcp.FastMCP` became `mcp.server.mcpserver.MCPServer`. Most tutorials online still show the 1.x import and fail on a current install with a confusing `No module named 'mcp.server.fastmcp'`.

The lab handles both:

```python
try:
    from mcp.server.mcpserver import MCPServer as _Server   # mcp >= 2.0
except ImportError:                                        # pragma: no cover
    try:
        from mcp.server.fastmcp import FastMCP as _Server   # mcp 1.x
    except ImportError as exc:
        print(f"MCP import failed ({exc}). Install the SDK:  pip install mcp", file=sys.stderr)
        raise SystemExit(1)
```

## Verify before you wire

Never register an MCP server you haven't confirmed loads. A broken server usually fails silently at agent startup and you'll spend an hour wondering why the tools aren't there.

```bash
cd labs && .venv/bin/python verify_mcp.py
```

Real output:

```
MCP server loaded. Tools registered:
  - search_entities: Find entities in the knowledge graph by name or description.
  - get_subgraph: Retrieve the smallest relevant subgraph around some entities.
  - add_knowledge: Store a new episode as validated graph memory.
  - graph_stats: Report the size and shape of the knowledge graph.

accepted: 2 entities, 1 edges
rejected: 0
Dana (person)
GRAPH EVIDENCE (answer only from these edges; say so if insufficient):
  - Dana --works_at--> Fabrikam [2025 .. present] (episode 1)
entities=2, edges=1, episodes=1, open_edges=1, aliases=0
```

Four tools registered, a write accepted through the gate, and a retrieval that came back cited. Now it's safe to register.

## Driver A: Copilot CLI

```bash
cd labs
copilot mcp add graphlab \
  --env GRAPHLAB_DB=$PWD/memory.db \
  -- $PWD/.venv/bin/python $PWD/mcp_server.py
```

Confirm:

```bash
copilot mcp list
copilot mcp get graphlab
```

Real output from `mcp add`:

```
Added server "graphlab"

graphlab
  Type: local
  Command: /path/to/labs/.venv/bin/python /path/to/labs/mcp_server.py
  Environment:
    GRAPHLAB_DB: ***
  Tools: * (all)
  Source: User
```

Note the `--` separator before the command. Everything after it is the command and its args. Without it, Copilot tries to parse your python path as a URL.

Config sources, in case you want the server scoped to one repo instead of your user:

| Scope | File |
|---|---|
| User | `~/.copilot/mcp-config.json` |
| Workspace | `.mcp.json` or `.github/mcp.json` |

Now use it:

```bash
copilot -p "Use the graphlab tools. Search for Alice, get her 1-hop subgraph \
as of 2025, and tell me where she worked. Cite the edges." \
  --model claude-opus-4.8 --allow-all-tools
```

Remove when you're done experimenting:

```bash
copilot mcp remove graphlab
```

## Driver B: Hermes Agent

Add to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  graphlab:
    command: "/absolute/path/to/labs/.venv/bin/python"
    args: ["/absolute/path/to/labs/mcp_server.py"]
    env:
      GRAPHLAB_DB: "/absolute/path/to/labs/memory.db"
    timeout: 60
    connect_timeout: 30
```

Restart Hermes. At startup it connects, discovers the tools, and registers them as:

```
mcp_graphlab_search_entities
mcp_graphlab_get_subgraph
mcp_graphlab_add_knowledge
mcp_graphlab_graph_stats
```

Those are then injected into every platform toolset, so the graph is available in every conversation without per-session setup. That is the meaningful difference from the Copilot flow: Hermes treats MCP tools as ambient capability rather than something you opt into per invocation.

Three Hermes-specific facts worth internalizing:

1. **No hot reload.** Config change means restart.
2. **Filtered environment.** Only `PATH`, `HOME`, `USER`, `LANG`, `LC_ALL`, `TERM`, `SHELL`, `TMPDIR` and `XDG_*` are inherited by the subprocess. Every other variable, including any API key, must be named explicitly under `env:`. That's a deliberate guard against leaking your whole shell environment to a third-party MCP server, and it is a good default that other clients don't have.
3. **Errors are redacted.** Credential-shaped patterns in MCP error messages are stripped before reaching the model.

## Two kinds of memory, one system

Hermes already has its own memory: durable facts, plus skills as procedural memory. Now it also has your graph. Keeping the boundary clear is worth doing deliberately:

| | Agent memory (Hermes) | Graph memory (yours) |
|---|---|---|
| Holds | Preferences, conventions, stable facts about the user | Entities, relationships, temporal state about a domain |
| Size | Small, curated, always in context | Large, retrieved on demand |
| Written by | The agent, deliberately | The ingestion pipeline, through a gate |
| Queried by | Always present in the prompt | Explicit tool call |

The failure mode is dumping domain facts into agent memory until every prompt drags a knowledge base it mostly doesn't need. Agent memory is for what must always be true. Graph memory is for what must be retrievable.

## Exercises

1. **Make the model cite.** Ask a question through your driver and require the answer to reference specific edges. Then ask something the graph cannot answer and confirm it reports the gap rather than inventing one. If it invents, strengthen the empty-result string in `get_subgraph`.

2. **Add a `close_fact` tool.** `store.invalidate()` exists but isn't exposed. Expose it, and decide deliberately whether an agent should be allowed to expire facts autonomously. Write down your reasoning, it's a real design decision.

3. **Scope it to a workspace.** Move the config from user scope to `.mcp.json` in a project directory and confirm the tools appear only there.

Next: measure the thing, because everything above is a hypothesis until you have numbers.
