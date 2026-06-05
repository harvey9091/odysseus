# ODYSSEUS AI HANDOFF CONTEXT

> **Condensed architecture intelligence for AI ingestion**
> **Version:** 0.9.1 | **Full reference:** ODYSSEUS_COMPLETE_SYSTEM_ARCHITECTURE.md

---

## PLATFORM IDENTITY

Odysseus is a **self-hosted AI assistant platform** (not just a chatbot). FastAPI backend + vanilla JS SPA frontend + SQLite + ChromaDB, deployed via Docker Compose (4 containers). Provides chat, agentic tool use, deep research, email, calendar, notes, tasks, documents, gallery, model management (cookbook), memory, and skills — all through one web UI.

## STACK SUMMARY

- **Backend:** Python 3.12, FastAPI, SQLAlchemy, uvicorn
- **Frontend:** Vanilla JS ES modules (no build), 189KB HTML + 1MB CSS + 73 JS modules
- **Database:** SQLite (`data/app.db`, 20+ tables), JSON config files, ChromaDB vectors
- **Docker:** 4 services — odysseus (:7000), chromadb (:8100), searxng (:8080), ntfy (:8091)
- **Auth:** bcrypt + TOTP 2FA + API tokens (ody_ prefix) + session cookies (7-day TTL)
- **Encryption:** Fernet at rest for secrets (data/.app_key)

## CRITICAL FILE MAP

| File | Lines | Role |
|------|-------|------|
| `app.py` | 1065 | Main orchestrator: middleware chain, 40+ route registrations, startup/shutdown lifecycle |
| `core/database.py` | 1858 | All SQLAlchemy models (Session, ChatMessage, Document, ModelEndpoint, ScheduledTask, etc.) |
| `core/auth.py` | 510 | Multi-user auth, bcrypt, TOTP 2FA, session tokens, privilege system |
| `core/session_manager.py` | 609 | Session CRUD with lazy hydration (metadata at boot, messages on first access) |
| `core/middleware.py` | 102 | CSP nonce, internal-tool token, require_admin() |
| `src/llm_core.py` | 1296 | Multi-provider LLM communication: streaming, fallback chains, dead-host cooldown |
| `src/agent_loop.py` | 2207 | Agentic execution: multi-round tool parsing/execution, system prompts |
| `src/agent_backend.py` | 328 | Agent ABC: OpenCode (built-in) + Hermes (external HTTP/SSE) |
| `src/agent_manager.py` | 198 | Thread-safe singleton agent provider manager |
| `src/tool_schemas.py` | 1228 | OpenAI function schemas for 60+ tools |
| `src/tool_index.py` | 476 | RAG tool selection via ChromaDB embeddings |
| `src/chat_handler.py` | 308 | Chat preprocessing: URLs, YouTube, images, presets |
| `src/endpoint_resolver.py` | 373 | Unified endpoint resolution with Tailscale fallback |
| `src/task_scheduler.py` | 2202 | Cron task execution with timezone + shared TTL cache |
| `src/deep_research.py` | 830 | IterResearch: Think→Search→Extract→Synthesize loop |
| `src/settings.py` | 249 | Centralized settings with 2s TTL cache |
| `src/memory.py` | 370 | JSON memory with Jaccard similarity |
| `services/search/core.py` | 436 | Search orchestrator: 6 providers with fallback chain |
| `services/memory/skills.py` | 642 | Skills manager: SKILL.md files with usage tracking |
| `services/hwfit/hardware.py` | 600 | GPU/CPU detection (NVIDIA, AMD, Apple) with SSH remote |
| `docker-compose.yml` | 141 | 4-service infrastructure definition |

## ARCHITECTURE PATTERNS

### 1. Provider-Agnostic LLM Layer (`src/llm_core.py`)
- `stream_llm()` — single function for all providers
- Provider detection by URL hostname: anthropic→native API, ollama→native API, openrouter/groq→OpenAI-compatible, default→OpenAI-compatible
- Dead-host cooldown: 20s after 2 consecutive failures (thread-safe)
- Fallback chains: `stream_llm_with_fallback()` tries ordered candidate list
- Shared httpx.AsyncClient with 100-connection pool
- Response cache: 128 entries, SHA-256 keyed
- Anthropic: native /v1/messages, prompt caching (ephemeral cache_control), x-api-key
- Ollama: native /api/chat, tool_calls normalization
- OpenAI: stream_options for usage, max_completion_tokens for reasoning models

### 2. Agent System
- `AgentManager` (thread-safe singleton) → `AgentBackend` ABC → OpenCode or Hermes
- OpenCode delegates to `agent_loop.stream_agent_loop()`
- Tool invocation: LLM writes fenced code blocks OR native function calling
- Tool selection: ChromaDB RAG from 60+ tool descriptions, top-K per message
- ALWAYS_AVAILABLE: bash, python, web_search, web_fetch, read_file, api_call, app_api
- Max rounds configurable, 60s per-tool timeout, 10K char output limit

### 3. SSE Streaming (No WebSocket)
- All real-time: chat, agent, shell, research use Server-Sent Events
- Events: delta, thinking, tool_start, tool_output, agent_step, web_sources, metrics, fallback, message_saved, [DONE]

### 4. Multi-Path Auth
- Session cookie → AuthManager (7-day TTL, bcrypt)
- Bearer token (ody_ prefix) → ApiToken DB table
- Internal-tool token (X-Odysseus-Internal-Token) → per-process random, agent loopback
- LOCALHOST_BYPASS → dev-only loopback skip
- Privileges: can_use_agent, can_use_bash, can_generate_images, etc.

### 5. Middleware Chain (order matters)
```
Request → CORS → SecurityHeaders (CSP nonce) → RequestTimeout (45s) → Auth → Handler
```

### 6. Persistence
- SQLite: 20+ tables (sessions, messages, documents, endpoints, tasks, etc.)
- JSON files: auth, sessions metadata, memory, settings, presets, integrations
- EncryptedText: Fernet encryption for secrets in DB columns
- Atomic writes: write-to-temp + fsync + os.replace for all JSON configs
- ChromaDB: tool index, memory vectors, document RAG

### 7. Search System
- 6 providers: SearXNG, Brave, DuckDuckGo, Google PSE, Tavily, Serper
- Configurable fallback chain (default: DuckDuckGo)
- File-based result cache with variable TTL
- Content extraction: BeautifulSoup web page parsing

### 8. Docker Infrastructure
- 4 services with health checks and dependency ordering
- PUID/PGID privilege dropping (entrypoint.sh)
- GPU overlays: NVIDIA (nvidia-container-toolkit) + AMD (ROCm)
- host.docker.internal for host Ollama access
- Bind mounts: data, logs, SSH keys, HuggingFace cache, local installs

## STARTUP SEQUENCE

```
app.py loaded by uvicorn
1. Register MIME types + Windows symlink fix
2. load_dotenv() + create FastAPI app
3. Add middleware: CORS → SecurityHeaders → Timeout → Auth
4. Mount static files
5. initialize_managers() → Memory, Skills, Sessions, Presets, ChatProcessor, etc.
6. Register 48 route modules
7. @startup: agent manager start, incognito purge, MCP connect, tool index warmup,
   LLM endpoint warmup, default tasks, skill backfill, task scheduler start
```

## KEY DATA FLOWS

### Chat: user msg → preprocess (URLs/YouTube/images) → context build (memory/skills/RAG/history) → stream_llm → SSE → save response → extract memory

### Agent: user msg → agent_backend.stream() → agent_loop → [system prompt + RAG tools → stream_llm → parse tool calls → execute tools → feed results back → loop] → SSE → save

### Research: topic → plan (LLM) → loop [queries (LLM) → search (6 providers) → extract (LLM) → synthesize (LLM) → check complete (LLM)] → final report → save

## EXTENSION CHEAT SHEET

| Task | Files to modify |
|------|----------------|
| New LLM provider | `src/llm_core.py` (_detect_provider + stream_llm), `src/endpoint_resolver.py` |
| New tool | `src/tool_schemas.py` (schema), `src/tool_index.py` (description), tool implementation |
| New agent backend | `src/agent_backend.py` (subclass ABC), register in `src/agent_manager.py` |
| New search provider | `services/search/providers.py` (impl), `core.py` (_call_provider), PROVIDER_INFO |
| New MCP server | `mcp_servers/new_server.py`, register in DB McpServer table |
| New API route | `routes/new_routes.py` (setup_*_routes → APIRouter), register in `app.py` |
| New UI panel | `static/index.html` (HTML), `static/js/new.js` (module), SPA route in `app.py` |
| New scheduled task | `src/task_scheduler.py` (action type), `static/js/tasks.js` (UI) |
| New DB model | `core/database.py` (SQLAlchemy model), run migration |

## CRITICAL WARNINGS

1. **Reserved usernames:** internal-tool, api, demo, system — never create real accounts with these
2. **Always use endpoint_resolver** — never hardcode LLM URLs
3. **Always scope by owner** — multi-user data isolation depends on it
4. **Use internal-tool token for loopback** — don't bypass auth middleware
5. **SQLite is single-writer** — concurrent writes can lock; PostgreSQL migration possible via DATABASE_URL
6. **Use atomic_write_json()** — prevents corruption on crash
7. **Shell tool = full system access** — restrict via can_use_bash privilege
8. **ChromaDB required for tool selection** — falls back to keyword matching if down
9. **MCP servers are subprocesses** — can hang/zombie, need monitoring
10. **Fernet key at data/.app_key** — if stolen, all encrypted data is compromised

## ENVIRONMENT VARIABLES (KEY ONES)

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_HOST` | localhost | Primary LLM host |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `XAI_API_KEY` | — | xAI/Grok API key |
| `SEARXNG_INSTANCE` | http://localhost:8080 | Search engine URL |
| `DATABASE_URL` | sqlite:///./data/app.db | Database connection |
| `AUTH_ENABLED` | true | Enable auth |
| `CHROMADB_HOST` | localhost | Vector store host |
| `CHROMADB_PORT` | 8100 | Vector store port |
| `AGENT_BACKEND` | opencode | Default agent |
| `EMBEDDING_URL` | — | Embedding API URL |
| `APP_PORT` | 7000 | Web UI port |
| `PUID` / `PGID` | 1000 | Container user/group ID |

## DEPENDENCY MAP

```
FastAPI (app.py)
├── core/database.py → SQLite (20+ tables)
├── core/auth.py → bcrypt + pyotp + data/auth.json
├── core/session_manager.py → data/sessions.json + DB
├── src/llm_core.py → httpx → External LLM APIs
├── src/agent_loop.py → llm_core + tool_index + tool_schemas + tool_implementations
├── src/tool_index.py → ChromaDB (odysseus_tool_index collection)
├── src/deep_research.py → search service + llm_core
├── src/task_scheduler.py → DB ScheduledTask + llm_core
├── services/search/ → SearXNG, Brave, DDG, Google, Tavily, Serper
├── services/memory/ → JSON + ChromaDB + LLM extraction
├── services/hwfit/ → nvidia-smi, rocm-smi, SSH
├── mcp_servers/ → stdio subprocesses (email, memory, image, rag)
└── static/ → FastAPI StaticFiles → Browser
```

## ROUTE REGISTRATION PATTERN

Every route file exports `setup_*_routes() -> APIRouter`:
```python
def setup_chat_routes() -> APIRouter:
    router = APIRouter(tags=["chat"])
    @router.post("/api/chat_stream")
    async def chat_stream(...): ...
    return router
```
Registered in `app.py`: `app.include_router(setup_chat_routes())`

47 route files covering: auth, chat, agent, sessions, documents, research, memory, skills, models, email, calendar, notes, tasks, gallery, cookbook, shell, TTS, STT, search, MCP, webhooks, presets, contacts, compare, signatures, vault, preferences, personal docs, history, diagnostics, cleanup, editor drafts, admin wipe, backup, hwfit, fonts, emoji, assistant, leads.

## SPA FRONTEND STRUCTURE

- **Entry:** `static/index.html` (189KB) — all panel HTML
- **Router:** `static/app.js` (172KB) — client-side routing, state
- **Styling:** `static/style.css` (1084KB) — CSS variables for themes
- **Modules:** `static/js/` (73 files) — ES modules, no build step
- **Key modules:** chat.js (215KB), document.js (413KB), settings.js (219KB), notes.js (227KB), emailLibrary.js (227KB), calendar.js (156KB), tasks.js (124KB), cookbook.js (101KB), theme.js (104KB), admin.js (107KB)
- **SPA routes:** /, /notes, /calendar, /cookbook, /email, /memory, /gallery, /tasks, /library

## PERFORMANCE PROFILE

- **Startup:** 5-10s (ChromaDB warmup + endpoint health checks)
- **Memory:** 250-400MB typical
- **Chat first token:** 200ms-5s
- **Agent round:** 2-30s
- **Research:** 2-30 minutes
- **Concurrency:** 100+ async requests, 100 connection pool, SQLite write bottleneck

## SCALING LIMITS

- Single-process (one uvicorn worker)
- SQLite single-writer (WAL mode helps)
- In-memory caches not shared across processes
- No horizontal scaling (designed for single-instance self-hosted)
- MCP subprocesses: one set per process

## KNOWN RISKS

- Global mutable state (dead-host maps, caches) — some protected by locks, some not
- Large monolithic files (agent_loop 2207, task_scheduler 2202, database 1858)
- No API versioning, no rate limiting, no audit logging
- Duplicate memory modules (src/memory.py + services/memory/memory.py)
- JSON file corruption risk (mitigated by atomic writes)
- MCP subprocess management fragile (stdio-based)

---

*This file is optimized for AI context window ingestion. For complete details, see ODYSSEUS_COMPLETE_SYSTEM_ARCHITECTURE.md.*
