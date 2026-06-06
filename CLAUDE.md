# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the agent (dev mode, auto-reload)
make dev                  # uvicorn on 127.0.0.1:8080

# Tests
make test                 # pytest tests/
pytest tests/test_graph.py -k "test_name"  # single test

# Lint / format
make lint                 # ruff check + format --check
make fmt                  # ruff format (auto-fix)

# DB init
make setup                # create Postgres tables, Qdrant collection
make setup-dogfood        # seed dogfood fixtures

# Infra shortcuts
make neo4j-shell          # cypher-shell into Neo4j
make graph-stats          # print Graphiti health

# Overlay
make overlay-install      # copy overlay/init.lua → ~/dotfiles and reload Hammerspoon
```

Config is read from `.env` at project root; defaults in `neuros/config.py` target the homelab hosts (`lts1`, `lts2`, `nas`).

## Architecture

NeurOS is a personal AI OS exposing a FastAPI server (`neuros/main.py`) that processes queries through a **LangGraph pipeline** (`neuros/graph.py`) and dispatches work to a registry of **skills** (`neuros/skills/`).

### Request lifecycle

```
POST /query
  → graph: intake → recall → [entity_query?] → think → act → store → respond
```

1. **intake** — normalize input, classify intent (`_classify_dogfood`, `_is_entity_query`)
2. **recall** — `MemoryManager.recall()` fans out to Qdrant (semantic) + Redis (recent session) + Graphiti (graph)
3. **entity_query** (conditional) — direct Neo4j/Graphiti lookup for "tell me about X" patterns
4. **think** — LLM call via `neuros/llm/client.py`; model selected by `neuros/llm/selector.py` (`REASONING→qwen35`, `FAST→gemma-4`, `VISION→qwen27-vision`)
5. **act** — execute skill from `SkillRegistry` if the LLM emitted a tool call
6. **dogfood** (conditional branch) — self-referential code read/improve/apply/commit flow; produces `ProposedChange` records stored in Postgres
7. **store** — `MemoryManager.store()` writes to Qdrant + Graphiti in parallel
8. **respond** — format `NeurOSResponse`

### Memory layer (`neuros/memory/`)

| Store | Role |
|---|---|
| **Qdrant** | Semantic vector search over all stored text |
| **Redis** | Short-term session history (recent turns) |
| **Postgres** | Durable structured storage: `ProposedChange`, timeline events |
| **Graphiti** (Neo4j) | Temporal knowledge graph; entity/relation extraction and search |

`MemoryManager` (singleton set by lifespan, accessed via `memory_module.manager`) is the single interface graph nodes use — nothing in `graph.py` imports stores directly.

### Skills (`neuros/skills/`)

Skills are stateless `BaseSkill` subclasses with `name`, `description`, `parameters` (OpenAI tool schema), and `async run(**params) → SkillResult`. `SkillRegistry.auto_discover()` walks the package tree at startup and registers all concrete subclasses.

Skill categories:
- `code/` — read, understand, improve, apply, commit, test (the "dogfood" flow)
- `infra/` — SSH commands, GPU server ops, NAS API
- `knowledge/` — remember, recall, capture, summarize
- `macos/` — Calendar, Reminders, system control
- `search/` — SearXNG web search

### Hammerspoon overlay (`overlay/init.lua`)

A Lua-based macOS floating panel (CMD+SHIFT+SPACE) that POSTs to `127.0.0.1:8080/query` via polling bridge (HTTP polling every 300ms for responses). The entire overlay is a single Lua file rendered as an `hs.webview`.

### LLM layer (`neuros/llm/`)

Uses `openai`-compatible HTTP client pointed at local inference endpoints. All models are self-hosted; no external API calls. `llm/registry.py` maps model names to `ModelConfig` (base_url + model_id). `llm/embedder.py` hits `lts1:8005` for embeddings.

## Key design patterns

- **`NeurOSState` TypedDict** flows through every LangGraph node — nodes read and return partial dicts merged by LangGraph.
- **`SkillResult.ok(data)` / `SkillResult.fail(error)`** are the only return types from skills; never raise from `run()`.
- **`ProposedChange`** is the approval gate for dogfood code edits — the agent writes proposals to Postgres; the user approves via `POST /proposals/{id}/approve` before `applier.py` writes to disk.
- Skills must remain **stateless** — all state lives in the memory stores or LangGraph state dict.
