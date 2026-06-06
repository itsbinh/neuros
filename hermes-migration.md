# Hermes → NeurOS Migration Audit

What's worth bringing from `~/.hermes` into NeurOS, and why. This is analysis only — no integrations yet.

---

## 1. Obsidian Vault as Second Brain (`hermes-vault/`, `vault/`)

**What it is:** PARA-structured Obsidian vault (`00-Home`, `01-Projects`, `02-Areas`, `03-Resources`, `04-Archive`, `05-Daily`) used as long-term institutional memory. Every session writes to a daily log. Curated notes live in `03-Resources/{patterns,mistakes,decisions,systems}/`.

**How it works:**
- Notes are embedded via `nomic-embed-text-v1.5` (768-dim) running as a dedicated llama.cpp container on lts1:8005
- Vectors stored in Qdrant on lts2:6333, collection `obsidian-notes`
- `vault-watch.py` — incremental watcher: embeds only changed/new notes, prunes stale Qdrant points (runs every 30 min)
- `obsidian-embed.py` — full re-index (runs nightly at 3am)
- `vault-query.py` — CLI semantic search tool
- `vault-sync/__init__.py` — Claude Code plugin that auto-embeds vault files on write (hooks into file write tool calls)

**Why bring it:**
NeurOS already has Qdrant + Graphiti for memory. The Obsidian vault adds a *curated, human-editable* knowledge layer that survives agent restarts and grows across sessions. The PARA structure and the write discipline (decisions, patterns, mistakes) is high-value institutional memory. The incremental watch + auto-embed pattern is more efficient than full re-index.

**What to extract:**
- The `vault-watch.py` incremental embed + Qdrant prune logic → adapt to NeurOS `MemoryManager`
- The PARA vault structure → use as the filesystem schema for NeurOS knowledge notes
- Collection naming convention and metadata schema (title, tags, path, updated)
- Auto-embed plugin hook pattern (embed on file write) → NeurOS dogfood skill could trigger re-embed after code changes

---

## 2. HermesBrain Plugin — Auto Capture (`plugins/hermesbrain/`)

**What it is:** A Claude Code plugin (~720 lines) that monitors every tool call and output, identifies "capture-worthy moments," and auto-writes them to the Obsidian vault.

**How it works:**
- Hooks into `post_tool_call` and `message_stop` events
- Pattern-matching on errors/tracebacks, decisions, "hard-won solutions" (bug fixes that took >3 attempts), user corrections, environment changes
- Extracts structured entries, runs dedup check before writing, then triggers incremental embed
- Also tracks a "lesson learned" queue that feeds into a nightly batch (`HermesBrain daily learning capture` cron at 23:45)

**Why bring it:**
NeurOS has a `store` node but it only runs at conversation end and doesn't classify what's worth keeping. HermesBrain's heuristic filtering (errors, corrections, decisions) avoids noise and makes the memory store signal-rich.

**What to extract:**
- Capture patterns dict (categories: mistake, decision, solution, environment_change, user_correction) — adapt into NeurOS `store` node or a dedicated classify-and-store step
- Dedup logic (check first 100 chars against existing Qdrant vectors before write)
- The "daily learning capture" cron → NeurOS could batch-promote high-score Qdrant entries into Graphiti as permanent entities nightly

---

## 3. Homelab Health Plugin (`plugins/homelab-health/`)

**What it is:** SSH-based infrastructure monitoring plugin — disk usage, container health, service status, Docker cleanup on lts1 and lts2.

**How it works:**
- SSH with strict `StrictHostKeyChecking=yes` and known-hosts pinned (never `AutoAddPolicy`)
- Tool schemas: `check_disk`, `check_containers`, `check_service`, `docker_prune`
- Returns JSON, handles auth via ssh-agent

**Why bring it:**
NeurOS's `SSHSkill` and `GPUServerSkill` overlap but lack the infrastructure-monitoring operations. The SSH safety posture (StrictHostKeyChecking) is better than the current `AutoAddPolicy` in NeurOS's SSHSkill.

**What to extract:**
- Replace `paramiko.AutoAddPolicy()` in `SSHSkill` with strict known-hosts policy
- Add `check_disk` and `check_containers` actions to `GPUServerSkill` or a new `InfraSkill`
- The Docker cleanup pattern (prune dangling images/volumes) is useful for homelab maintenance

---

## 4. Prompt Injection Defense (`skills/prompt-injection-defense/`)

**What it is:** Three-layer defense against prompt injection attacks.

**How it works:**
- `inject_detector.py` — pattern-based detection (regex), covers: role confusion, command override, prompt leakage, context poisoning, tool hijacking, obfuscation, social engineering. Returns a risk score (weighted sum); threshold-based block.
- `output_monitor.py` — post-agent output scanner, flags suspicious commands in generated text before they're executed
- `url_scanner.py` — checks URLs in tool inputs against known-malicious patterns before fetch

**Why bring it:**
NeurOS takes user text → LLM → skills with no sanitization layer. As it expands to web search and link ingestion, injection risk grows. The `inject_detector.py` is self-contained, zero-dependency, and fast.

**What to extract:**
- `inject_detector.py` → run in the `intake` graph node before any LLM call. Block or flag inputs scoring above threshold.
- `url_scanner.py` → integrate into `SearchSkill` and any future link-fetching skill
- Pattern list is the most valuable artifact — maintain it as `neuros/security/injection_patterns.py`

---

## 5. Vault Knowledge Capture Skill (`skills/vault-knowledge-capture/`)

**What it is:** Explicit skill for structured knowledge capture into the vault with categorized output paths.

**How it works:**
- Accepts category + content, writes to the correct PARA path (e.g. mistakes → `03-Resources/mistakes/<topic>.md`)
- Frontmatter with date, tags, session_id
- Triggers incremental embed after write
- Has "what NOT to capture" guidance baked into the trigger heuristics

**Why bring it:**
NeurOS's `CaptureSkill` is a flat Qdrant upsert with no categorization. The PARA-structured capture with category routing means recall is much more targeted — "what did we decide about X" vs "what broke" are different queries hitting different paths.

**What to extract:**
- Category routing logic + PARA path mapping
- Frontmatter schema (date, tags, category, session_id)
- "Not to capture" heuristics (avoid trivial one-offs, raw data dumps, already-in-memory facts)

---

## 6. Tool Reliability Tracker (`tooling/tool_reliability.py`)

**What it is:** JSON-backed event log for every tool call: success/failure, duration, error message, consecutive failure count.

**How it works:**
- `record_event(tool, status, issue, duration_ms, context)` appends to `~/.hermes/state/tool_reliability.json`
- Tracks per-tool stats: success count, failure count, avg duration, consecutive failures, most common issues
- CLI: `python tool_reliability.py report` → ranked table of flaky tools

**Why bring it:**
NeurOS skills swallow exceptions via `SkillResult.fail()` with no observability into which skills fail most, how long they take, or what the failure modes are. This tracker is 100 lines of stdlib-only Python.

**What to extract:**
- Adapt into NeurOS as a Postgres-backed skill telemetry table (or just a JSON file in the project root for dev)
- Hook into `SkillResult.ok()` / `SkillResult.fail()` to auto-record — zero skill-code changes needed
- The `consecutive_failures` metric is useful for alerting: if a skill fails 3x in a row, flag it in the health endpoint

---

## 7. Context Compactor (`tooling/context_compactor.py`)

**What it is:** Parses agent working notes / markdown files and extracts only `decisions`, `current_state`, and `next_steps` sections — dropping everything else.

**How it works:**
- Section-header matching (normalized), bullet extraction
- Outputs compact JSON: `{decisions: [...], current_state: [...], next_steps: [...], dropped_items_count: N}`
- Used to summarize long working docs before injecting into context

**Why bring it:**
NeurOS's `think` node injects raw recall results into the LLM prompt. As context grows (Graphiti + Qdrant + Redis merged results), prompt size blooms. A compactor that strips non-essential content from recalled documents keeps prompts tight.

**What to extract:**
- The section-extraction logic → apply to Qdrant recall results before injecting into `think` prompt
- Extend to handle NeurOS vault notes (which follow same PARA markdown structure)

---

## 8. LLM Inference Service Management (`skills/llm-inference-service-management/`)

**What it is:** Knowledge skill documenting how to manage llama.cpp/vLLM on lts1 — startup, OOM debugging, VRAM optimization, model switching, the config-model mismatch pitfall.

**Key insight — the Config-Model Mismatch pitfall:**
When switching models, `llm/registry.py` must reflect only what the server actually has loaded (`/v1/models`). If the registry lists a model the server doesn't have, the skill selector silently routes to it and errors. The authoritative truth is the Docker Compose file at `/mnt/main_pool/Docker/llamacpp/docker-compose.yml` on lts1.

**Why bring it:**
NeurOS's `llm/registry.py` has the same mismatch risk. If a model is unloaded (e.g., VRAM pressure swaps it out), the selector will fail. Currently there's no fallback or detection.

**What to extract:**
- Add a startup check in `main.py` lifespan: hit `lts1_base_url/v1/models`, compare to registry entries, warn on mismatch
- Add a model-not-found fallback in `select_model()` → fallback to `model_local` (mac mini) if primary is unavailable
- Document the compose file location as source of truth in `CLAUDE.md`

---

## 9. Ingest-Link Skill (`skills/ingest-link/`)

**What it is:** Skill for ingesting URLs — detects source type (YouTube, paper, blog, GitHub), extracts content appropriately (transcript for YT, abstract+methods for papers, article text for blogs), summarizes, and stores to vault with tags.

**How it works:**
- YouTube → `youtube-transcript.py` (via `youtube_transcript_api`)
- Papers → fetch PDF/abstract, extract via `pdfplumber` or HTML parsing
- Blogs/docs → `requests` + `BeautifulSoup`
- All → LLM summarize → vault capture with source URL, date, tags

**Why bring it:**
NeurOS has `SearchSkill` (SearXNG) but no ingestion pipeline. Ingesting links is the natural complement to search — find something interesting, capture it to memory for future recall.

**What to extract:**
- Source-type detection logic → new `IngestSkill` in `neuros/skills/knowledge/`
- YouTube transcript extraction → adapt `youtube-transcript.py`
- The LLM-summarize-then-store pattern (not raw-dump) → apply to NeurOS `CaptureSkill`

---

## 10. Daily Digest Email (`skills/daily-digest-email/`)

**What it is:** Composes and sends a daily email with: GitHub trending (AI/OSS/local-LLM), Reddit highlights (r/LocalLLaMA, r/SideProject), curated macOS tool picks. Strict format with section quotas (8-15 GitHub items, 4-8 reads).

**Why bring it:**
Lower priority for NeurOS core but useful as a scheduled task via the `CronCreate` mechanism once the agent is stable.

**What to extract:**
- The SearXNG query patterns for GitHub trending and Reddit (can feed into `SearchSkill`)
- Email composition format spec (section quotas prevent bloat)
- The cron scheduling pattern → NeurOS could expose a `/schedule` endpoint for recurring tasks

---

## 11. Ops-Brain Failure Patterns (`plugins/hermes-ops-brain/`)

**What it is:** Operational memory plugin with a `failure_patterns.json` codifying 10+ known-bad patterns with severity and actionable advice, plus a canonical `host_registry.json` with the full infra map.

**Provides 6 tools:**
- `ops_health` — SSH to lts1/lts2, TCP port checks on Qdrant/SearXNG/Redis/llamacpp
- `ops_host_registry` — Returns canonical machine map (roles, IPs, service URLs)
- `ops_tool_reliability` — Per-tool success/failure stats
- `ops_record_tool_event` — Writes tool events + pushes last 20 failures to Redis
- `ops_failure_advice` — Pattern-matches input against known-bad patterns (wrong Python path, docker prune without dry-run, wrong Qdrant host, retry amplification, argument-jitter loops) and returns fix advice
- `ops_redis_cache` — get/set/clear Redis keys under `hermes:ops:` namespace

**Guard hook:** `pre_tool_call` blocks: (a) Hermes scripts with wrong Python, (b) bare `docker system prune`, (c) same terminal command that failed 2+ times in a session.

**Why bring it:**
`ops_failure_advice` is a "known-bad pattern database" — when a skill fails, check it before retrying blindly. The `host_registry.json` is the canonical infrastructure map NeurOS needs (same homelab: Mac Mini / LTS1 / LTS2 / Synology).

**What to extract:**
- `failure_patterns.json` → seed a NeurOS `infra/known_issues.json` consumed by `SSHSkill` and `GPUServerSkill` on error
- `host_registry.json` → supersedes hardcoded host values in `config.py`; make it a loadable fixture
- The guard hook pattern (block repeated failing commands) → NeurOS `act` node can detect consecutive `SkillResult.fail()` from same skill and route to fallback

---

## 12. Agent Policy & Safe Execution (`tooling/agent_policy.yaml`, `tooling/safe_exec.sh`)

**What it is:**
- `agent_policy.yaml`: Canonical execution policy — deep mode triggers (complex_multi_step, high_risk_change, cross_machine_coordination), 5-step deep flow (inspect→plan→confirm→execute→verify), safety rules (destructive_requires_approval, prefer_sandbox), failure handling (one alternative then report root cause + 2-3 options), reflection fields required after meaningful tasks.
- `safe_exec.sh`: Shell wrapper detecting risky patterns before executing: `rm`, `mv` with wildcards, `git reset --hard`, `git push --force`, `docker prune`, `systemctl restart`, `iptables`, writes to `/etc`. Logs all executions, enforces 120s timeout, requires `--approve` flag for risky commands.

**Why bring it:**
NeurOS's `act` node invokes skills with no risky-pattern guard. The `agent_policy.yaml` reflection requirement (structured output after complex tasks) maps to NeurOS's `store` node — it should be storing not just the raw text but a structured summary of what was decided/changed.

**What to extract:**
- Risky pattern list from `safe_exec.sh` → NeurOS skill parameter validation (especially `SSHSkill` command, `CalendarSkill` scripts)
- Deep-mode triggers → when NeurOS sees `high_risk_change` intent, invoke extra verification step before `act`
- Reflection field schema (decisions, current_state, next_steps) → structured `store` node output

---

## 13. Multi-Agent Delegation (`scripts/candice_escalate.py`)

**What it is:** Spawns a Claude Code CLI subagent for complex tasks. Creates a timestamped artifact in `~/.hermes/multi-agent/candice/`, updates `state.json` agent registry, appends to `events.jsonl`. Builds a structured escalation prompt from task description + context.

**Why bring it:**
NeurOS's `dogfood` flow handles self-improvement but has no mechanism to delegate out-of-scope tasks to a stronger reasoner. The `candice_escalate.py` pattern — escalation prompt → artifact → CLI invocation → result capture — is exactly what NeurOS needs when the local models hit their reasoning ceiling.

**What to extract:**
- Escalation prompt template (includes task description, context, exit criteria)
- Agent registry pattern (event log + state.json) for tracking delegated tasks
- Could become a NeurOS skill: `EscalateSkill` that POST to a `/escalate` endpoint or invokes `claude -p` as a subprocess

---

## Priority Order for Migration

| # | Item | Value | Effort |
|---|------|-------|--------|
| 1 | Prompt Injection Defense (`inject_detector.py`) | High | Low |
| 2 | Tool Reliability Tracker | High | Low |
| 3 | HermesBrain capture heuristics | High | Medium |
| 4 | Inference startup model-mismatch check | High | Low |
| 5 | Ops-Brain failure patterns + host registry | High | Low |
| 6 | Agent policy / safe exec risky pattern list | High | Low |
| 7 | Obsidian vault structure + incremental embed | High | Medium |
| 8 | Vault Knowledge Capture (PARA routing) | Medium | Medium |
| 9 | Ingest-Link skill | Medium | Medium |
| 10 | Multi-agent delegation (EscalateSkill) | Medium | Medium |
| 11 | SSH strict host-key policy | Medium | Low |
| 12 | Context compactor for recall pruning | Medium | Low |
| 13 | Homelab Health infra ops | Low | Low |
| 14 | Daily Digest email | Low | High |
