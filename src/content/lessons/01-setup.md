---
title: "Setup: Hermes and Copilot CLI"
order: 1
part: "Part 0 — Orientation"
summary: "Get one of the two drivers running, plus the lab repo. Ten minutes, no API key."
minutes: 15
hands_on: true
---

Pick a driver. You only need one, but the course shows both because they teach different halves of the idea.

## The lab code

```bash
git clone https://github.com/brianbaldock/graph-engineering-course
cd graph-engineering-course/labs
python3 -m venv .venv
.venv/bin/pip install pytest mcp
```

Check it works:

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected output:

```
...............                                                          [100%]
15 passed in 0.06s
```

If those 15 tests pass, every lab in this course will run on your machine. Nothing else is required for Parts 1 through 3.

## Driver A: GitHub Copilot CLI

Best if you want to *feel* the routing idea. One binary, many models, one subscription.

```bash
copilot --version
gh auth status          # Copilot inherits GitHub auth
```

Model selection is a flag, which is exactly the lever this course is about:

```bash
# cheap, mechanical work
copilot -p "Summarize labs/graphlab/validate.py in five bullets" \
  --model claude-haiku-4.5 --allow-all-tools

# expensive, high-judgment work
copilot -p "Critique the validation gate in labs/graphlab/validate.py. \
What class of bad extraction still gets through?" \
  --model claude-opus-4.8 --effort high --allow-all-tools
```

<div class="callout">
<strong>Non-negotiable flag.</strong> In <code>-p</code> (non-interactive) mode you must pass <code>--allow-all-tools</code>. Without it, Copilot hits its first permission prompt and hangs forever with no output.
</div>

There is no `copilot models` subcommand. To discover what's available, ask Copilot itself:

```bash
copilot -p "list available models" --allow-all-tools --model claude-sonnet-4.5
```

## Driver B: Hermes Agent

Best if you want durable memory and MCP tools present in *every* conversation, without re-wiring per session.

Hermes has a native MCP client. Servers listed in `~/.hermes/config.yaml` are connected at startup, their tools discovered, and those tools injected into every platform toolset:

```yaml
mcp_servers:
  graphlab:
    command: "/absolute/path/to/labs/.venv/bin/python"
    args: ["/absolute/path/to/labs/mcp_server.py"]
    env:
      GRAPHLAB_DB: "/absolute/path/to/labs/memory.db"
    timeout: 60
```

Tools land in the registry as `mcp_{server}_{tool}`, so the four tools you'll build become `mcp_graphlab_search_entities`, `mcp_graphlab_get_subgraph`, `mcp_graphlab_add_knowledge`, and `mcp_graphlab_graph_stats`.

Two things to know before Lesson 8:

- **Restart is required.** There's no hot-reload for MCP servers. Add config, restart the agent.
- **The environment is filtered.** Hermes does not pass your whole shell environment to MCP subprocesses. Only `PATH`, `HOME`, `USER`, `LANG`, `TERM`, `SHELL`, `TMPDIR` and `XDG_*` are inherited. Anything else, including API keys, must be named explicitly under `env:`. That's a deliberate credential-leak guard, and it's the reason `GRAPHLAB_DB` appears above.

## Use absolute paths everywhere

MCP servers are launched as subprocesses with a working directory you do not control. Every path in an MCP config must be absolute. This is the single most common setup failure, in both drivers.

Get yours:

```bash
cd graph-engineering-course/labs && pwd
```

## Optional: the production track

Only needed for Lesson 11. Skip it for now.

- Docker, for Neo4j
- `uv`, for running the Graphiti MCP server
- An `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` if you want real LLM extraction instead of the deterministic offline one

Everything in Parts 1 through 3 runs free and offline.

Next: what a knowledge graph actually buys you that a vector store doesn't.
