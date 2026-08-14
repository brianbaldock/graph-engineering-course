---
title: "The production track: Neo4j and Graphiti"
order: 10
part: "Part 4: Production"
summary: "When SQLite stops being enough, and the verified Graphiti MCP config the viral article got wrong."
minutes: 30
hands_on: true
sources:
  - graphiti-mcp-server
  - graphiti-mcp-pypi-404
---

Everything so far ran on SQLite with no server and no API key. That was deliberate: you can't learn an architecture while fighting infrastructure. But there's a point where the toy store stops being appropriate.

## When to graduate

Move to a real graph database when you hit one of these, not before:

- **Traversal depth.** Recursive multi-hop queries in SQL get ugly fast. Cypher expresses "all paths from A to B up to depth 5" in a line.
- **Concurrent writers.** SQLite's write lock is a single lane. Multiple ingestion workers will serialize on it.
- **Scale.** Tens of thousands of nodes with heavy traversal is where a purpose-built graph engine starts to matter.
- **Hybrid search built in.** Graphiti gives you vector, BM25, and graph search over the same store, which saves you building the fusion layer from Lesson 2 by hand.

If none of those apply, the SQLite store is genuinely fine. "It's not a real graph database" is not a reason. Cost and operational burden are real, and a system you can debug beats one you can only admire.

## Neo4j

```bash
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password-here \
  neo4j:5
```

Browser UI at `http://localhost:7474`, Bolt protocol on `7687`.

<div class="callout">
<strong>Do not run this exposed.</strong> The default Neo4j container binds all interfaces. On a laptop behind NAT that's survivable; on a VPS it's a graph database with a known default port and a password you probably reused. Bind to localhost, put it on a private network, and change the password on first login.
</div>

## Graphiti

Graphiti is a temporal knowledge graph library for agent memory. It does the things this course had you build by hand: bi-temporal edges, entity resolution, incremental updates without full recomputation, and hybrid retrieval.

The library is on PyPI:

```bash
pip install graphiti-core
```

## The MCP server config, verified

Here is where the viral article went wrong. It gave:

```json
{ "mcpServers": { "graphiti": { "command": "uvx", "args": ["graphiti-mcp"] } } }
```

`graphiti-mcp` is not a package. PyPI returns 404. The MCP server ships inside the repository, not as a distributable, so you run it from a checkout:

```bash
git clone https://github.com/getzep/graphiti.git
cd graphiti/mcp_server
uv sync
```

Then the configuration, matching the shape in the project's own README:

```json
{
  "mcpServers": {
    "graphiti-memory": {
      "transport": "stdio",
      "command": "/absolute/path/to/uv",
      "args": [
        "run",
        "--isolated",
        "--directory", "/absolute/path/to/graphiti/mcp_server",
        "--project", ".",
        "main.py",
        "--transport", "stdio",
        "--database-provider", "neo4j"
      ],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "your-password",
        "OPENAI_API_KEY": "sk-...",
        "MODEL_NAME": "gpt-5-mini"
      }
    }
  }
}
```

<div class="callout">
<strong>Verify the entrypoint against your checkout.</strong> The server's entry filename has changed across versions (<code>main.py</code> in the current README, <code>graphiti_mcp_server.py</code> in older docs and in mirrored copies of the instructions). Look at what's actually in your <code>mcp_server/</code> directory and use that. This is the same class of mistake as the fabricated package name: copying a config instead of checking it.
</div>

<div class="callout">
<strong>The provider flag is not optional.</strong> Graphiti's MCP server defaults to <strong>FalkorDB</strong>, not Neo4j. Setting <code>NEO4J_URI</code> and friends in <code>env</code> does not switch the backend; without <code>--database-provider neo4j</code> the server starts against FalkorDB and quietly ignores every Neo4j variable you just set. You get a running server, no error, and an empty graph where your data should be. Confirm which backend you are actually on before you load anything into it.
</div>

For Hermes, the same thing in `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  graphiti:
    command: "/absolute/path/to/uv"
    args:
      - "run"
      - "--isolated"
      - "--directory"
      - "/absolute/path/to/graphiti/mcp_server"
      - "--project"
      - "."
      - "main.py"
      - "--transport"
      - "stdio"
      - "--database-provider"
      - "neo4j"
    env:
      NEO4J_URI: "bolt://localhost:7687"
      NEO4J_USER: "neo4j"
      NEO4J_PASSWORD: "your-password"
      OPENAI_API_KEY: "sk-..."
      MODEL_NAME: "gpt-5-mini"
    timeout: 120
```

For Copilot CLI, note the `--` separator before the command:

```bash
copilot mcp add graphiti \
  --env NEO4J_URI=bolt://localhost:7687 \
  --env NEO4J_USER=neo4j \
  --env NEO4J_PASSWORD=your-password \
  --env OPENAI_API_KEY=sk-... \
  -- /absolute/path/to/uv run --isolated \
     --directory /absolute/path/to/graphiti/mcp_server \
     --project . main.py --transport stdio
```

Then confirm it actually came up, the same way you did in Lesson 8:

```bash
copilot mcp get graphiti
```

## Secrets

The configs above have API keys inline because that's what every vendor README shows. Don't ship that.

- `~/.hermes/config.yaml` and `~/.copilot/mcp-config.json` are plaintext files in your home directory. Treat them as secrets: `chmod 600`, never commit them, and never paste them into a chat with an agent.
- Prefer env-var indirection or a secrets manager where the client supports it.
- Give the Neo4j user the minimum rights the server needs. The MCP server does not need to be able to drop your database.
- Remember Hermes filters the subprocess environment, so anything the server needs must be named explicitly under `env:`. That's inconvenient exactly once and protective every time after.

## What you keep from the hand-built version

Graphiti does not replace your judgment, and three things you built stay yours:

1. **The validation gate.** Graphiti will happily store what its extractor produces. If you want a grounding check and a closed relation vocabulary, that is still your code, sitting in front of the ingest call.
2. **The routing policy.** `MODEL_NAME` above sets the extraction model. That single line is the cheap-extraction half of Lesson 7. The expensive-reasoning half is still your call at query time.
3. **The measurements.** Lesson 9's metrics apply unchanged. A library does not exempt you from measuring your own cache hit rate.

## Exercise: port and compare

Take the sample corpus from `labs/graphlab/sample_data.py` and ingest it through Graphiti. Then compare against your hand-built graph:

- Did Graphiti's extractor resolve "Northwind Inc" to "Northwind" without your alias table?
- Did it handle "Alice left Northwind" as a temporal close, or as a new relation?
- How many edges did it produce compared to your 9? More is not automatically better. Check whether the extra ones are supported by the text.
- What did it cost, per episode?

This comparison is the real deliverable. You now have a baseline you built yourself, which means you can evaluate a library instead of adopting it on faith. That is a rarer skill than knowing Cypher.

Next: the wrap-up, and how to tell good architecture advice from the other kind.
