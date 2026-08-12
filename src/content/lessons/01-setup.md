---
title: "Setup: Hermes and Copilot CLI"
order: 1
part: "Part 0 — Orientation"
summary: "Get one of the two drivers running, plus the lab repo. Ten minutes, no API key."
minutes: 15
hands_on: true
sources:
  - copilot-cli-install
  - hermes-agent-install
  - copilot-cli-docs
  - hermes-agent-docs
---

Pick a driver. You only need one, but the course shows both because they teach different halves of the idea.

## The lab code

```bash
git clone https://github.com/brianbaldock/graph-engineering-course
cd graph-engineering-course/labs
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Check it works:

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected output:

```
......................                                                   [100%]
25 passed in 0.16s
```

If those tests pass, every lab in this course will run on your machine. Nothing else is required for Parts 1 through 3.

## Driver A: GitHub Copilot CLI

Best if you want to *feel* the routing idea. One binary, many models, one subscription.

Install it ([full instructions](https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli)):

```bash
# any platform, via npm
npm install -g @github/copilot

# or macOS and Linux, via the install script
curl -fsSL https://gh.io/copilot-install | bash
```

Copilot CLI needs an active Copilot subscription and authenticates with your existing GitHub credentials. Confirm it landed:

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

There is no `copilot models` subcommand, and asking a model to list its own availability is not verification. Use `auto` and let Copilot pick, then check what it selected:

```bash
copilot -p "list available models" --allow-all-tools --model auto
```

Model availability is account-specific and changes. Treat any model list in this course as "what worked on the author's account when the lesson was written," and confirm against your own before building a policy on it.

## Driver B: Hermes Agent

Best if you want durable memory and MCP tools present in *every* conversation, without re-wiring per session.

Install it ([full instructions](https://hermes-agent.nousresearch.com/docs/getting-started/installation)):

```bash
# Linux, macOS, WSL2, Termux
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

```powershell
# Windows, in PowerShell
iex (irm https://hermes-agent.nousresearch.com/install.ps1)
```

On Windows or macOS you can instead run the [Hermes Desktop installer](https://hermes-agent.nousresearch.com/), which sets up both the desktop app and the CLI. After installing, `hermes setup` walks you through connecting a model.

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

Tools land in the registry as `mcp__{server}__{tool}` (two underscores on each side of the server name), so the four tools you'll build become `mcp__graphlab__search_entities`, `mcp__graphlab__get_subgraph`, `mcp__graphlab__add_knowledge`, and `mcp__graphlab__graph_stats`.

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

Only needed for Lesson 10. Skip it for now.

- Docker, for Neo4j
- `uv`, for running the Graphiti MCP server
- An `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` if you want real LLM extraction instead of the deterministic offline one

Everything in Parts 1 through 3 runs free and offline.

Next: what a knowledge graph actually buys you that a vector store doesn't.
