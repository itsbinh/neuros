# NeurOS

> Personal AI operating system. Built for one. Runs local. No cloud.

## What it is

NeurOS is an ADHD-focused personal agent that runs entirely on your own hardware. It combines local LLM inference, vector memory, structured storage, and macOS automation into a single coherent system — no SaaS, no multi-tenant, no data leaving your network.

Think of it as a personal OS layer: you type or speak a request, NeurOS recalls context, reasons with the right model, takes action through skills, and remembers what happened. All on-prem.

## Architecture

```
┌──────────────┐      ┌─────────────────────────────────────────┐
│  MacBook     │      │              lts1 (GPU Server)           │
│  :8000 Agent │─────▶│  :8000 llama.cpp router                 │
│  FastAPI +   │      │    Qwen3-27B vision                     │
│  Hammerspoon │─────▶│    Qwen3-35B-A3B fast                   │
│  overlay     │      │  :8005 embed server                      │
└──────┬───────┘      └─────────────────────────────────────────┘
       │
       │                    ┌──────────────────────────────────┐
       │                    │         lts2 (Services)           │
       │              ┌─────▶ :5432 Postgres 16                 │
       │              │     :6333 Qdrant                        │
       │              ├────▶ :6379 Redis 7                      │
       │              │     :8888 SearXNG                       │
       │              └────────────────────────────────────────┘
       │
       │                    ┌──────────────────────────────────┐
       │                    │      mac-mini (MLX Server)        │
       │                    │  :8001 Gemma 4 27B               │
       │                    │  131K context, offline fallback   │
       │                    └──────────────────────────────────┘
```

### Agent Flow

```
intake → recall → think → act → store → respond
```

1. **Intake** — parse user input, detect task type (vision / reasoning / fast)
2. **Recall** — semantic search Qdrant + recent Redis context + Postgres facts
3. **Think** — route to the right model via `selector.py`
4. **Act** — dispatch skills (macOS, infra, knowledge, search)
5. **Store** — embed result → Qdrant, log interaction → Postgres
6. **Respond** — stream back through FastAPI → Hammerspoon overlay

## Stack

| Layer       | Technology                           |
|-------------|--------------------------------------|
| Agent API   | FastAPI + LangGraph                  |
| LLM (GPU)   | llama.cpp router on lts1             |
| LLM (local) | MLX / Gemma 4 on mac-mini            |
| Embeddings  | Dedicated embed server on lts1:8005  |
| Vector DB   | Qdrant on lts2:6333                  |
| Cache       | Redis 7 on lts2:6379                 |
| Structured  | Postgres 16 on lts2:5432             |
| Search      | SearXNG on lts2:8888                 |
| Overlay     | Hammerspoon (Lua)                    |
| Infra       | Paramiko SSH, Synology HTTP API      |

## Setup

### Prerequisites

- Python 3.11+
- All servers running (lts1, lts2, mac-mini)
- SSH key-based access to lts1, lts2, nas

### Quick start

```bash
# 1. Configure environment
cp .env.example .env   # fill real passwords/hosts

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Initialize databases
make setup             # Postgres tables + Qdrant collection

# 4. Verify the stack
make test-stack        # ping all models, embeddings, memory round-trip

# 5. Start the agent
make dev               # FastAPI on :8000

# 6. Install Hammerspoon overlay
make overlay-install   # copy init.lua to ~/.hammerspoon/
                       # reload Hammerspoon: CMD+SHIFT+R

# 7. First interaction
# CMD+SHIFT+SPACE → type "hello" → get your first NeurOS response
```

## Roadmap

- [x] Project scaffold and architecture
- [ ] Core agent loop (LangGraph graph)
- [ ] LLM client with model routing
- [ ] Memory layer (Qdrant + Redis + Postgres)
- [ ] macOS skills (Reminders, Calendar, System)
- [ ] Infra skills (SSH, GPU monitoring, NAS)
- [ ] Knowledge skills (capture, recall, summarize)
- [ ] Search skill (SearXNG integration)
- [ ] Hammerspoon overlay with streaming display
- [ ] Voice input/output pipeline
- [ ] Proactive suggestions for ADHD focus

## License

MIT
