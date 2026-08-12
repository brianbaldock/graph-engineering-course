# Graph Engineering

A hands-on course in agentic graph engineering: knowledge-graph memory for AI
agents, driven with **Hermes Agent** and **GitHub Copilot CLI**.

Live site: https://agenticgraphs.dev

## Why this exists

A claim went viral: *"90% of Anthropic engineers shifted to agentic graphs. No
more prompting."* The percentages are unsourced and drifted between retellings
(70% in earlier variants), and the video attached to the most-shared post was
the Claude Code release demo rather than a graph lecture.

The architecture underneath is real and worth learning. This course keeps the
architecture and audits the rest.

It also fixes a config: the accompanying article told readers to run
`uvx graphiti-mcp`. That package does not exist on PyPI (404). The verified
Graphiti MCP configuration is in Lesson 10.

## The one idea

> Spend intelligence exactly where intelligence is needed.

| Work | Volume | Judgment | Configuration |
|---|---|---|---|
| Extraction (text → entities, edges) | Very high | Low, mechanical | Cheap model, cached prefix, batched |
| Traversal and reasoning | Low | High, multi-hop | Frontier model, small precise context |

## Quick start

```bash
git clone https://github.com/brianbaldock/graph-engineering-course
cd graph-engineering-course/labs
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python -m pytest tests/ -q         # 22 passed
.venv/bin/python -m graphlab.pipeline        # full pipeline, no API key
.venv/bin/python -m graphlab.seed memory.db  # seed the graph the MCP lesson uses
.venv/bin/python verify_mcp.py               # confirm the MCP server behaves
```

No API key, no database server, no cloud account for Parts 1 through 3.

## What's in `labs/`

| File | What it is |
|---|---|
| `graphlab/store.py` | Temporal knowledge graph on SQLite. Edges carry `valid_from`/`valid_until` and provenance. |
| `graphlab/validate.py` | The validation gate. Closed relation vocabulary, normalization, grounding checks, real calendar dates. |
| `graphlab/extract.py` | Extraction with a stable cached prefix. Free offline backend plus the real Anthropic shape. |
| `graphlab/ingest.py` | The single ingestion boundary. Every write path goes through it, so temporal closes cannot be skipped. |
| `graphlab/policy.py` | Loads `routing_policy.yaml` and clamps the retrieval caps it actually enforces. |
| `graphlab/pipeline.py` | End-to-end: episode, extract, validate, commit, retrieve. |
| `graphlab/seed.py` | Wipe-and-rebuild the demo graph used by the MCP lesson. |
| `mcp_server.py` | Exposes the graph over MCP to Hermes and Copilot CLI. |
| `routing_policy.yaml` | The routing policy. Its header states exactly which keys are enforced and which are operator policy. |
| `tests/` | 22 tests covering the gate, temporal queries, retrieval bounds, and the MCP close regression. |

## Authorship

Written by Brian Baldock with substantial assistance from Hermes, an AI agent, collaborating since May 2026. Hermes did research, wrote and ran the lab code, executed verification, and drafted prose under Brian's direction. Brian reviewed the work and is responsible for the published text and labs.

The principles in these lessons come from operating a real agent deployment. The `graphlab` package is a teaching implementation of those principles, not the production memory system behind that work.

## Wiring it into an agent

**Copilot CLI:**

```bash
cd labs
copilot mcp add graphlab --env GRAPHLAB_DB=$PWD/memory.db \
  -- $PWD/.venv/bin/python $PWD/mcp_server.py
```

**Hermes Agent** (`~/.hermes/config.yaml`):

```yaml
mcp_servers:
  graphlab:
    command: "/absolute/path/to/labs/.venv/bin/python"
    args: ["/absolute/path/to/labs/mcp_server.py"]
    env:
      GRAPHLAB_DB: "/absolute/path/to/labs/memory.db"
```

## Site development

```bash
nvm use 22
npm install
npm run dev
npm run build && npx astro check
```

Astro 5, Tailwind v4, deployed to GitHub Pages by Actions. CI runs the lab
tests and the MCP verification before it will deploy the site, because a
course that ships broken code is worse than no course.

## Standing rule

Every command on the site was run before it was published. Where a widely
circulated config was wrong, the course says so and gives the verified one.

## Sources

- Ajay (@ajay4ai), *Master Graph Engineering With Opus 5*, X Article, 2026-08-09. The architectural source, credited in full.
- [getzep/graphiti](https://github.com/getzep/graphiti) for the production track.
- Anthropic docs for prompt caching and the Batch API.

## License

Code MIT, prose CC BY 4.0. The boundary is stated explicitly in [`LICENSE`](LICENSE) and [`LICENSE-CONTENT`](LICENSE-CONTENT): MIT covers `labs/` and the site implementation, CC BY 4.0 covers the lesson prose in `src/content/lessons/`. Quoted third-party material stays under its own license.

Attribution for the prose: Graph Engineering by Brian Baldock, https://agenticgraphs.dev, CC BY 4.0.
