# ODYSSEUS COMPLETE SYSTEM ARCHITECTURE

> **Version:** 0.9.1 | **Last Updated:** 2026 | **Status:** Living Document
> **Purpose:** Complete technical intelligence layer for the Odysseus AI platform

---

## TABLE OF CONTENTS

1. [Project Overview](#1-project-overview)
2. [Complete Folder Structure Analysis](#2-complete-folder-structure-analysis)
3. [File-by-File Analysis](#3-file-by-file-analysis)
4. [Frontend System Architecture](#4-frontend-system-architecture)
5. [Backend System Architecture](#5-backend-system-architecture)
6. [AI System Architecture](#6-ai-system-architecture)
7. [Agent System Analysis](#7-agent-system-analysis)
8. [Database / Storage / Memory](#8-database--storage--memory)
9. [Docker + Infrastructure Analysis](#9-docker--infrastructure-analysis)
10. [Environment Variable Analysis](#10-environment-variable-analysis)
11. [API Flow Analysis](#11-api-flow-analysis)
12. [Authentication + Security](#12-authentication--security)
13. [Feature-by-Feature Deep Analysis](#13-feature-by-feature-deep-analysis)
14. [Current Custom Modifications Analysis](#14-current-custom-modifications-analysis)
15. [Complete Runtime Execution Flow](#15-complete-runtime-execution-flow)
16. [System Dependency Graph](#16-system-dependency-graph)
17. [Future Development Guide](#17-future-development-guide)
18. [Performance + Scaling Analysis](#18-performance--scaling-analysis)
19. [Known Risks + Technical Debt](#19-known-risks--technical-debt)
20. [Complete Final System Summary + AI Context Handoff](#20-complete-final-system-summary)

---

# 1. PROJECT OVERVIEW

## What Odysseus Is

Odysseus is a **self-hosted, full-stack AI assistant platform** that provides a comprehensive suite of AI-powered tools through a single web application. It is NOT a simple chatbot — it is an autonomous AI operating system combining:

- **Multi-provider LLM orchestration** (OpenAI, Anthropic, Ollama, OpenRouter, Groq, xAI/Grok, Mistral, DeepSeek, Google, Together, Fireworks)
- **Agentic tool execution** (60+ tools with RAG-based selection via ChromaDB embeddings)
- **Dual agent backends** (OpenCode built-in + Hermes external HTTP/SSE service)
- **Deep research engine** (IterResearch-style Think→Search→Extract→Synthesize loop)
- **Full productivity suite** (email, calendar, notes, tasks, documents, gallery, cookbook)
- **Model management** (download, serve, manage local/remote models via vLLM, SGLang, llama.cpp, Ollama)
- **MCP server integration** (stdio + SSE transport for external tool servers)
- **Scheduled task automation** (cron-based with timezone support, event bus triggers)
- **Memory + Skills system** (Jaccard similarity + ChromaDB vector store)
- **Multi-user authentication** (bcrypt, TOTP 2FA, API tokens, session cookies)

## System Purpose

Odysseus serves as a **personal AI infrastructure layer** — a single self-hosted deployment that provides:

1. **Chat interface** with persistent memory and context management
2. **Agent mode** with full system access (shell, Python, file I/O, web search, document editing)
3. **Research engine** that autonomously searches, extracts, and synthesizes information
4. **Email client** with IMAP/SMTP, multi-account support, AI summarization
5. **Calendar** with CalDAV sync (Radicale, Nextcloud, Apple, Fastmail)
6. **Notes/Tasks** (Google Keep-style with checklists, reminders, due dates)
7. **Document editor** with versioning, suggestions, code highlighting (34 editor modules)
8. **Gallery** with AI-powered image generation, upscaling, background removal
9. **Cookbook** for managing local/remote model servers (download, serve, diagnose GPU)
10. **Skills** system for reusable AI procedures stored as structured markdown

## Core Philosophy

- **Self-hosted first**: Everything runs locally or on your infrastructure
- **Provider-agnostic**: Single codebase works with any OpenAI-compatible, Anthropic, or Ollama endpoint
- **Agent-native**: The LLM is not just a chatbot — it has tools to act on the world
- **Privacy-conscious**: Encrypted storage at rest (Fernet), no external telemetry
- **Cross-platform**: Windows compatibility layer, Docker-native, Tailscale-aware

## Primary Architecture Style

- **Monolithic FastAPI application** with modular internal organization
- **SPA frontend** (single index.html, 70+ ES modules, no build step)
- **SQLite default** with SQLAlchemy ORM (swappable to PostgreSQL via DATABASE_URL)
- **SSE streaming** for all real-time communication (chat, agent, shell)
- **Event-driven** task scheduling with shared TTL cache (singleflight pattern)

## High-Level System Map

```
┌──────────────────────────────────────────────────────────────────┐
│                        BROWSER (SPA)                             │
│  index.html → app.js → chat.js / document.js / settings.js ...  │
│  70+ ES modules │ style.css (1MB) │ SW.js │ manifest.json       │
└────────────────────────┬─────────────────────────────────────────┘
                         │ HTTP/SSE
┌────────────────────────▼─────────────────────────────────────────┐
│                     FASTAPI (app.py)                              │
│  CORS → SecurityHeaders → RequestTimeout → Auth Middleware       │
│  40+ route modules │ Static files │ SPA fallback                 │
├──────────────────────────────────────────────────────────────────┤
│  src/ (business logic)  │  core/ (infrastructure)                │
│  llm_core.py           │  database.py (SQLAlchemy)               │
│  agent_loop.py         │  auth.py (bcrypt + TOTP)                │
│  agent_backend.py      │  session_manager.py                     │
│  chat_handler.py       │  middleware.py (CSP + internal token)   │
│  deep_research.py      │  atomic_io.py                           │
│  tool_index.py         │  platform_compat.py                     │
│  task_scheduler.py     │  constants.py / models.py / exceptions  │
├──────────────────────────────────────────────────────────────────┤
│  services/ (microservice-like modules)                           │
│  search/ (6 providers) │ memory/ (skills + vectors)              │
│  shell/ (exec)         │ tts/ (Kokoro + API)                    │
│  stt/ (Whisper + API)  │ youtube/ (transcripts)                 │
│  hwfit/ (GPU detect)   │ research/ (deep research)              │
│  faces/ (recognition)  │ docs/ (document service)               │
├──────────────────────────────────────────────────────────────────┤
│  mcp_servers/ (built-in MCP)  │  companion/ (LAN pairing)       │
│  email_server.py               │  routes.py (QR code pairing)   │
│  memory_server.py              │  pairing.py (CSRF-safe)        │
│  image_gen_server.py           └────────────────────────────────┤
│  rag_server.py                                                   │
└──────────────────────────────────────────────────────────────────┘
         │              │              │              │
    ┌────▼────┐  ┌──────▼─────┐  ┌────▼─────┐  ┌────▼────┐
    │ ChromaDB│  │  SearXNG   │  │   ntfy   │  │ Ollama/ │
    │ :8100   │  │  :8080     │  │  :8091   │  │ vLLM    │
    └─────────┘  └────────────┘  └──────────┘  └─────────┘
```

---

# 2. COMPLETE FOLDER STRUCTURE ANALYSIS

## `/` (Project Root)

**Purpose:** Application entry point and build configuration.
**Key files:**
- `app.py` (1065 lines) — Main FastAPI orchestrator. Registers all middleware, routes, lifecycle events.
- `docker-compose.yml` (141 lines) — 4-service Docker infrastructure.
- `Dockerfile` (48 lines) — Python 3.12-slim with system deps.
- `requirements.txt` (42 lines) — 20 core Python dependencies.
- `package.json` — NPM deps for frontend (marked.js, highlight.js, etc.)
- `.env.example` (172 lines) — Complete environment variable documentation.
- `setup.py` — Package setup.
- `pyproject.toml` — Pytest configuration.

**Runtime importance:** `app.py` is the single entry point. `uvicorn app:app` starts everything.

## `/core/` (Infrastructure Layer)

**Purpose:** Foundational modules that all other code depends on. Zero business logic.
**Dependencies:** SQLAlchemy, bcrypt, pyotp, cryptography
**Connected systems:** Every module in the application.

| File | Lines | Purpose |
|------|-------|---------|
| `database.py` | 1858 | SQLAlchemy models (20+ tables), engine, session factory, EncryptedText type |
| `auth.py` | 510 | Multi-user auth with bcrypt, TOTP 2FA, session tokens, privilege system |
| `session_manager.py` | 609 | Session lifecycle: lazy hydration, CRUD, auto-archive, message persistence |
| `middleware.py` | 102 | Security headers (CSP nonce), internal tool token, require_admin() |
| `models.py` | 85 | Pure data models (ChatMessage, Session) separate from DB models |
| `constants.py` | 41 | App-wide constants (paths, timeouts, env vars) |
| `atomic_io.py` | 44 | Atomic JSON writes (write-to-temp + fsync + os.replace) |
| `platform_compat.py` | 204 | Cross-platform helpers (Windows path normalization, symlink detection) |
| `exceptions.py` | 30 | Custom exception hierarchy |

## `/src/` (Business Logic Layer)

**Purpose:** All application logic — LLM communication, agent systems, tool execution, settings, integrations.
**Files:** 76 Python files + 1 subdirectory
**Dependencies:** httpx, chromadb-client, fastembed, numpy

### Critical src/ files:

| File | Lines | Purpose |
|------|-------|---------|
| `llm_core.py` | 1296 | Core LLM communication: multi-provider streaming, dead-host cooldown, connection pooling |
| `agent_loop.py` | 2207 | Streaming agent loop: multi-round tool execution, system prompts, UI conventions |
| `agent_backend.py` | 328 | Agent backend ABC: OpenCode + Hermes implementations, SSE event contract |
| `agent_manager.py` | 198 | Thread-safe singleton agent provider manager with health-based fallback |
| `tool_schemas.py` | 1228 | OpenAI-compatible function tool schemas for 60+ tools |
| `tool_index.py` | 476 | RAG-based tool selection using ChromaDB embeddings |
| `chat_handler.py` | 308 | Chat preprocessing: preset validation, URL extraction, YouTube transcripts |
| `endpoint_resolver.py` | 373 | Unified endpoint resolution with Tailscale fallback, provider URL builders |
| `model_discovery.py` | 204 | Model endpoint discovery across hosts/ports, Tailscale scanning |
| `task_scheduler.py` | 2202 | Background scheduler: cron/timezone support, shared TTL cache, housekeeping |
| `deep_research.py` | 830 | IterResearch engine: Think→Search→Extract→Synthesize loop |
| `settings.py` | 249 | Centralized settings with 2s TTL cache, DEFAULT_SETTINGS |
| `memory.py` | 370 | Memory manager: JSON storage, inline commands, Jaccard similarity |
| `embeddings.py` | 254 | Embedding client: HTTP API priority, fastembed ONNX fallback |
| `mcp_manager.py` | 429 | MCP server connection manager: stdio + SSE transport |
| `integrations.py` | 493 | API integration presets: Miniflux, Gitea, Linkding, Home Assistant |
| `event_bus.py` | 126 | Event automation: fire_event() for task triggers |
| `webhook_manager.py` | 227 | Outgoing webhooks: SSRF protection, HMAC-SHA256 signing |
| `config.py` | 208 | Pydantic settings configuration |
| `app_initializer.py` | 115 | Component initialization: creates all manager instances |

## `/routes/` (API Layer)

**Purpose:** FastAPI route handlers. Each file is an APIRouter with tagged endpoints.
**Files:** 47 Python files
**Pattern:** Each file exports `setup_*_routes() -> APIRouter`

### All route files:

| File | Purpose |
|------|---------|
| `auth_routes.py` | Login, setup, 2FA, user management |
| `chat_routes.py` (1227) | `/api/chat`, `/api/chat_stream`, context injection |
| `agent_routes.py` | Agent backend listing, switching |
| `session_routes.py` | Session CRUD, archive, fork, auto-sort |
| `document_routes.py` | Document CRUD, versioning |
| `document_helpers.py` | Document processing utilities |
| `research_routes.py` | Deep research start/status/results |
| `memory_routes.py` | Memory CRUD, search |
| `skills_routes.py` | Skills CRUD, search, publish |
| `model_routes.py` | Model endpoint management, discovery |
| `email_routes.py` | Email account management, send/read |
| `email_helpers.py` | Email processing utilities |
| `email_pollers.py` | Background IMAP polling |
| `calendar_routes.py` | CalDAV sync, event CRUD |
| `note_routes.py` | Notes/checklists CRUD |
| `task_routes.py` | Scheduled task management |
| `gallery_routes.py` | Gallery albums, images, AI editing |
| `gallery_helpers.py` | Image processing utilities |
| `cookbook_routes.py` | Model serving, downloading |
| `cookbook_helpers.py` | Cookbook utilities |
| `shell_routes.py` | Shell command execution, streaming |
| `upload_routes.py` | File upload handling |
| `tts_routes.py` | Text-to-speech synthesis |
| `stt_routes.py` | Speech-to-text transcription |
| `search_routes.py` | Web search API |
| `embedding_routes.py` | Embedding generation |
| `mcp_routes.py` | MCP server management |
| `webhook_routes.py` | Webhook CRUD |
| `preset_routes.py` | Chat presets management |
| `contacts_routes.py` | CardDAV contact management |
| `compare_routes.py` | Model comparison |
| `signature_routes.py` | Email signature management |
| `vault_routes.py` | Secret/credential storage |
| `prefs_routes.py` | User preferences |
| `personal_routes.py` | Personal document RAG |
| `history_routes.py` | Chat history search |
| `diagnostics_routes.py` | System diagnostics |
| `cleanup_routes.py` | Data cleanup tasks |
| `editor_draft_routes.py` | Editor draft persistence |
| `admin_wipe_routes.py` | Admin data wipe |
| `backup_routes.py` | Backup/restore |
| `hwfit_routes.py` | Hardware/GPU detection |
| `font_routes.py` | Font management |
| `emoji_routes.py` | Emoji picker data |
| `assistant_routes.py` | Personal assistant features |

## `/services/` (Service Layer)

**Purpose:** Microservice-like modules encapsulating specific capabilities.
**Pattern:** Each service has `__init__.py`, core implementation, and optional `service.py` wrapper.

### services/search/ (9 files)
- `core.py` (436) — Search orchestrator with provider fallback chain
- `providers.py` (547) — 6 provider implementations: SearXNG, Brave, DuckDuckGo, Google PSE, Tavily, Serper
- `content.py` (360) — Web page content extraction, key points, TLDR, quotes, statistics
- `analytics.py` (136) — Search analytics, error logging, rate limit tracking
- `ranking.py` (127) — Result ranking algorithm
- `query.py` (128) — Query enhancement, cache duration calculation
- `cache.py` (57) — Search result caching
- `service.py` (95) — Service wrapper

### services/memory/ (8 files)
- `memory.py` (359) — MemoryManager: JSON storage, Jaccard similarity, inline commands
- `memory_extractor.py` (547) — LLM-driven memory extraction from conversations
- `memory_vector.py` (175) — ChromaDB vector store for semantic memory search
- `skills.py` (642) — SkillsManager: SKILL.md file management, usage tracking
- `skill_extractor.py` (209) — Skill extraction from conversations
- `skill_format.py` (444) — SKILL.md format: YAML frontmatter + structured markdown
- `service.py` (137) — Memory service wrapper

### services/hwfit/ (7 files)
- `hardware.py` (600) — GPU detection (NVIDIA, AMD, Apple), CPU/RAM/disk, SSH remote probing
- `fit.py` (527) — Model fit estimation (VRAM requirements, quantization)
- `image_models.py` (374) — Image model compatibility checking
- `models.py` (232) — Model metadata and specifications
- `profiles.py` (229) — Hardware profiles for recommendations

### services/shell/ (2 files)
- `service.py` (162) — ShellService: safe command execution with timeout, streaming

### services/tts/ (2 files)
- `tts_service.py` (283) — Multi-provider TTS: local Kokoro, OpenAI API, browser Web Speech

### services/stt/ (2 files)
- `stt_service.py` (207) — Multi-provider STT: local faster-whisper, OpenAI API, browser

### services/leadhunter/ (2 files) **NEW**
- `service.py` — LeadHunterService: Product Hunt and beta lead discovery, lead scoring, Listmonk sync, campaign metrics

### services/youtube/ (2 files)
- `youtube_handler.py` (265) — YouTube transcript extraction, comment fetching

### services/research/ (3 files)
- `service.py` (166) — Research service wrapper
- `research_handler.py` (463) — Deep research orchestration

### services/docs/ (2 files)
- `service.py` (89) — Document service

### services/faces/ (1 file)
- Face recognition service

## `/mcp_servers/` (Built-in MCP Servers)

**Purpose:** MCP (Model Context Protocol) servers that run as subprocesses, communicating via stdio.
**Pattern:** Each server uses `mcp.server.Server` with `stdio_server()` transport.

| File | Lines | Purpose |
|------|-------|---------|
| `_common.py` | 19 | Shared constants: MAX_OUTPUT_CHARS, timeouts, truncate() |
| `email_server.py` | 1594 | Full email MCP: list, read, send, reply, multi-account IMAP/SMTP |
| `memory_server.py` | 209 | Memory MCP: list, add, edit, delete, search |
| `image_gen_server.py` | 167 | Image generation MCP: DALL-E/GPT-image via OpenAI-compatible API |
| `rag_server.py` | 145 | RAG MCP: list indexed files, add/remove directories |

## `/static/` (Frontend)

**Purpose:** Complete SPA frontend — no build step, served directly by FastAPI.

| File/Dir | Size | Purpose |
|----------|------|---------|
| `index.html` | 189KB | Main SPA shell with all panel HTML |
| `login.html` | 26KB | Login/setup page |
| `landing.html` | 43KB | Landing page |
| `app.js` | 172KB | Core application JS (router, state, init) |
| `style.css` | 1084KB | Complete CSS (themes, responsive, all components) |
| `sw.js` | 5KB | Service worker for offline support |
| `manifest.json` | 0.5KB | PWA manifest |
| `js/` (73 files) | — | ES modules (see Section 4) |
| `fonts/` (7 items) | — | Web fonts |
| `lib/` (6 items) | — | Third-party JS libraries |

## `/companion/` (LAN Device Pairing)

**Purpose:** QR-code-based device pairing for LAN access.
- `routes.py` (236) — Companion bridge routes
- `pairing.py` — CSRF-safe pairing token minting

## `/backend/` (Provider Abstraction Layer)

**Purpose:** Pluggable provider interfaces for future external integrations (leads, enrichment, etc.).

### backend/providers/leads/ (3 files)
- `base_provider.py` — Abstract `LeadProvider` ABC with `fetch_leads()`, `validate_lead()`, `get_provider_name()`, `is_enabled`; `Lead` Pydantic schema
- `mock_provider.py` — `MockLeadProvider`: deterministic test leads, used by `/api/leads/test`

## `/scripts/` (CLI Tools)

**Purpose:** Command-line utilities for managing Odysseus subsystems.
**Pattern:** `scripts/odysseus-<subsystem>` shell scripts + Python utilities.

Key scripts: `odysseus`, `odysseus-backup`, `odysseus-calendar`, `odysseus-contacts`, `odysseus-cookbook`, `odysseus-docs`, `odysseus-gallery`, `odysseus-logs`, `odysseus-mail`, `odysseus-mcp`, `odysseus-memory`, `odysseus-notes`, `odysseus-personal`, `odysseus-preset`, `odysseus-research`, `odysseus-sessions`, `odysseus-signature`, `odysseus-skills`, `odysseus-tasks`, `odysseus-theme`, `odysseus-webhook`

Python utilities: `add_hwfit_models.py`, `check-docker-gpu.sh`, `claim_ownerless.py`, `diffusion_server.py`, `fix_paths.py`, `hf_download.py`, `index_documents.py`, `migrate_faiss_to_chroma.py`, `update_database.py`

## `/data/` (Runtime Data)

**Purpose:** All persistent runtime data. Bind-mounted into Docker.
**Contents:**
- `app.db` — SQLite database (all DB models)
- `auth.json` — User accounts, passwords, sessions
- `sessions.json` — Session metadata cache
- `memory.json` — Memory entries
- `settings.json` — Application settings
- `skills/` — SKILL.md files organized by category
- `uploads/` — User file uploads
- `generated_images/` — AI-generated images
- `tts_cache/` — Cached TTS audio
- `personal_docs/` — RAG-indexed personal documents
- `deep_research/` — Saved research reports
- `fastembed_cache/` — Local ONNX embedding models
- `huggingface/` — HuggingFace model cache
- `ssh/` — SSH keys for Cookbook remote servers
- `scheduled_emails.db` — Scheduled email queue
- `.app_key` — Fernet encryption key

## `/config/` (Service Configuration)

- `searxng/settings.yml` — SearXNG search engine configuration template

## `/docker/` (Docker Extras)

- `entrypoint.sh` (87) — PUID/PGID privilege dropping, CUDA detection
- `gpu.nvidia.yml` — NVIDIA GPU passthrough overlay
- `gpu.amd.yml` — AMD ROCm GPU passthrough overlay

## `/tests/` (Test Suite)

**Files:** 88 test files using pytest + pytest-asyncio

## `/docs/` (Project Website)

Landing page and demo media (gifs, webm videos, screenshots)

## `/licenses/` (Attribution)

Apache-2.0 (DeepResearch), MIT (llmfit, opencode)

---

# 3. FILE-BY-FILE ANALYSIS

## app.py — Main Application Orchestrator (1065 lines)

**Purpose:** The single entry point that wires together the entire application.

**Execution role:** Loaded by uvicorn (`uvicorn app:app`). Everything starts here.

**Startup sequence:**
1. `register_static_mime_types()` — Force .js/.mjs MIME types (Windows compat)
2. Windows symlink fix — `HF_HUB_DISABLE_SYMLINKS=1` for UNC paths
3. `load_dotenv(encoding="utf-8-sig")` — Load .env with BOM tolerance
4. Create FastAPI app with metadata
5. CORS middleware — configurable origins via `ALLOWED_ORIGINS`
6. `SecurityHeadersMiddleware` — CSP nonce, X-Frame-Options, nosniff
7. `RequestTimeoutMiddleware` — 45s default, exempt paths for streaming/research/uploads
8. `AuthMiddleware` — Cookie sessions, Bearer tokens (ody_ prefix), internal-tool bypass, LOCALHOST_BYPASS
9. Static file mount with cache-busting (no-cache for .js/.css/.html)
10. `initialize_managers()` — Create all component instances
11. Register 40+ route modules
12. Startup event handler:
    - Agent manager start
    - Incognito session purge
    - Upload cleanup
    - Background monitor
    - MCP server connections
    - Tool index warmup
    - LLM endpoint warmup + keepalive
    - Default task creation
    - Skill owner backfill
    - Task scheduler start
    - Null-owner sweep
    - Nightly skill audit cron
13. Shutdown event handler:
    - Agent manager stop
    - Upload cleanup cancel
    - Task scheduler stop
    - Webhook manager close
    - MCP disconnect
14. SPA route fallbacks: `/`, `/notes`, `/calendar`, `/cookbook`, `/email`, `/memory`, `/gallery`, `/tasks`, `/library` → index.html

**Middleware chain (order matters):**
```
Request → CORS → SecurityHeaders → RequestTimeout → Auth → Route Handler → Response
```

**Token cache:** In-memory dict with dirty flag for API tokens. Loaded from DB on first request, refreshed on write.

**Critical interaction:** The `AuthMiddleware` has multiple auth paths:
1. Session cookie → validate against AuthManager sessions
2. Bearer token (ody_ prefix) → validate against ApiToken table
3. Internal-tool token (X-Odysseus-Internal-Token) → grant synthetic "internal-tool" user
4. LOCALHOST_BYPASS → skip auth for 127.0.0.1/::1 requests (dev only)

## core/database.py — SQLAlchemy Models (1858 lines)

**Purpose:** All database models, engine configuration, and ORM relationships.

**Engine:** SQLite default (`sqlite:///./data/app.db`), configurable via `DATABASE_URL`.

**Key patterns:**
- `TimestampMixin` — `created_at`, `updated_at` on all models
- `EncryptedText` TypeDecorator — Fernet encryption at rest via `src.secret_storage`
- Owner-scoped rows — `owner` column for multi-user isolation
- Composite indexes — optimized for common queries

**Database Models:**

| Model | Purpose |
|-------|---------|
| `Session` | Chat sessions with endpoint, model, owner, folder, RAG flag |
| `ChatMessage` | Individual messages with role, content, model, token counts |
| `Document` | Editor documents with language, content, versions |
| `DocumentVersion` | Document version history |
| `GalleryAlbum` | Photo albums |
| `GalleryImage` | Individual images with prompt, model, size, quality |
| `EmailAccount` | IMAP/SMTP account configs (encrypted passwords) |
| `ModelEndpoint` | LLM API endpoints with base_url, API key, cached models |
| `McpServer` | MCP server configs (transport, command, disabled tools) |
| `Comparison` | Model comparison results |
| `Signature` | Email signatures (encrypted) |
| `ApiToken` | Bearer API tokens (ody_ prefix) |
| `Webhook` | Outgoing webhook configs |
| `UserTool` | Custom user-defined tools |
| `UserToolData` | Data storage for user tools |
| `CrewMember` | Multi-agent crew configurations |
| `ScheduledTask` | Cron tasks with prompt, schedule, timezone, next_run |

**Session model details:**
- `id` — String primary key (UUID)
- `name` — Display name
- `endpoint_url` — LLM API URL for this session
- `model` — Model identifier
- `owner` — Username (null = legacy/shared)
- `rag` — Boolean RAG mode
- `archived` — Boolean archive flag
- `folder` — Organization folder
- `headers` — JSON request headers
- `last_accessed` — Updated on any access
- `last_message_at` — Updated only on actual message persistence

## core/auth.py — Authentication System (510 lines)

**Purpose:** Multi-user authentication with password hashing, session tokens, 2FA.

**AuthManager class:**
- **Password hashing:** bcrypt with `bcrypt.gensalt()`
- **Session tokens:** `secrets.token_hex(32)`, 7-day TTL
- **Persistence:** `data/auth.json` (atomic writes) + `data/sessions.json`
- **TOTP 2FA:** pyotp with backup codes
- **Privilege system:** Per-user capabilities (can_use_agent, can_use_bash, can_generate_images, etc.)
- **Reserved usernames:** `internal-tool`, `api`, `demo`, `system` (never real accounts)
- **Thread safety:** RLock for sessions, Lock for setup

**Auth flow:**
1. First boot → `is_configured == False` → setup endpoint creates admin
2. Login → verify bcrypt password → check 2FA if enabled → generate session token
3. Request → AuthMiddleware checks cookie or Bearer token → resolves username
4. Admin check → `require_admin()` checks role, internal-tool token, or auth-disabled

**DEFAULT_PRIVILEGES:**
```python
{
    "can_use_agent": True,
    "can_use_browser": True,
    "can_use_bash": False,      # Shell access is opt-in
    "can_use_documents": True,
    "can_use_research": True,
    "can_generate_images": True,
    "can_manage_memory": True,
    "max_messages_per_day": 0,  # 0 = unlimited
    "allowed_models": [],       # Empty = all models
}
```

## core/session_manager.py — Session Lifecycle (609 lines)

**Purpose:** Chat session management with lazy hydration pattern.

**Lazy hydration:** At boot, only session metadata loads from `sessions.json`. Full message history loads on first `get_session()` call. This keeps startup fast even with hundreds of sessions.

**Key operations:**
- `create_session()` — New session with UUID
- `get_session()` — Load with lazy message hydration
- `delete_session()` — Remove with message cleanup
- `archive_session()` — Soft-delete
- `mark_important()` — Pin session
- `update_name()` — Rename
- `truncate_session()` — Limit message count
- `replace_history()` — Replace entire message list
- Auto-archive old sessions, delete empty ones

## src/llm_core.py — LLM Communication Layer (1296 lines)

**Purpose:** The core abstraction layer for all LLM provider communication.

**LLMConfig:** DEFAULT_TIMEOUT=30, STREAM_TIMEOUT=300, MAX_RETRIES=3

**Provider detection** (URL hostname-based):
- `anthropic.com` → Anthropic native API
- `ollama` or `:11434` → Ollama native API
- `openrouter.ai` → OpenRouter (extra headers)
- `groq.com` → Groq
- Everything else → OpenAI-compatible

**Dead-host cooldown system:**
- `_HOST_FAIL_THRESHOLD = 2` consecutive failures before cooling
- `DEAD_HOST_COOLDOWN = 20.0` seconds
- Thread-safe via `_host_health_lock` (threading.Lock)
- Any success resets the failure counter

**Shared httpx.AsyncClient:**
- Connection pooling: `max_connections=100`
- Keepalive for model endpoints
- Per-request timeout configuration

**Response cache:** 128 entries max, SHA-256 key from (url, model, messages, temp, max_tokens)

**Anthropic native API handling:**
- Message format conversion (system/assistant/user/tool roles)
- `tool_use` / `tool_result` content blocks
- Prompt caching: ephemeral `cache_control` on system prompts and tool schemas
- `x-api-key` header authentication
- `anthropic-version: 2023-06-01` header

**Ollama native API handling:**
- `/api/chat` format (not OpenAI-compatible)
- `tool_calls` normalization (string arguments → parsed objects)
- Thinking tokens support

**OpenAI-compatible handling:**
- `stream_options: {"include_usage": True}` for token counting
- `max_completion_tokens` for o1/o3/o4/gpt-4.5/gpt-5 models
- Standard chat completion format

**Streaming protocol (SSE events):**
```
data: {"delta": "text chunk"}
data: {"thinking": true, "delta": "reasoning token"}
data: {"type": "tool_start", ...}
data: {"type": "tool_output", ...}
data: {"type": "web_sources", "data": [...]}
data: {"type": "metrics", "data": {"tokens_in": N, "tokens_out": N}}
data: {"type": "fallback", "model": "..."}
data: [DONE]
```

**Fallback chains:** `stream_llm_with_fallback()` — pre-content failure triggers next candidate in the chain. Configured via settings for chat, utility, vision model types.

**Thinking model support:** Qwen3, QwQ, DeepSeek-R1, MiniMax — preserves thinking tokens in separate `thinking` field.

**Gemini thought_signature:** Preserved in `extra_content` for multi-round coherence.

## src/agent_loop.py — Streaming Agent Loop (2207 lines)

**Purpose:** The core agentic execution loop. Wraps `stream_llm()` with multi-round tool execution.

**How it works:**
1. System prompt injected with tool rules and UI conventions
2. LLM generates response with optional fenced code blocks (tool calls)
3. Tool blocks parsed, executed, results formatted and fed back
4. Loop continues until LLM stops calling tools or hits MAX_AGENT_ROUNDS
5. All output streamed as SSE events

**Tool invocation method:** LLM writes fenced code blocks with tool name as language tag:
```
```bash
ls -la /home
```
```

**System prompt components:**
- `_AGENT_PREAMBLE` — Tool access announcement
- `_AGENT_RULES` — Detailed usage rules for each tool, email handling, calendar, notes, scheduling
- `_API_AGENT_RULES` — Rules for API/function-call mode (prefer native tool calling)
- UI conventions — Markdown link deep-links (`[Name](#session-id)`, `[Title](#document-id)`, etc.)

**Key behaviors:**
- BIAS TOWARD ACTION on edit requests
- After tool success: one sentence confirmation, no re-verification
- After tool failure: retry with fix OR tell user, never go silent
- Three ways to end: DONE (sanity-check first), BLOCKED (explain why), or keep going
- Bulk email: use bulk_email tool, never loop individual operations
- Email UIDs from tool output, never list row numbers
- Multiple accounts: call list_email_accounts, use exact account value

**MCP disabled tool loading:** `_load_mcp_disabled_map()` reads per-server disabled tools from DB.

## src/agent_backend.py — Agent Backend Abstraction (328 lines)

**Purpose:** Abstract base class for pluggable agent backends.

**AgentBackend ABC methods:**
- `stream()` — Main entry point, yields SSE events
- `initialize()` — Called at startup
- `shutdown()` — Called at shutdown
- `is_healthy()` — Health check
- `get_info()` — Metadata for API/UI

**SSE Event Contract:**
```
delta, thinking, tool_start, tool_output, agent_step, web_sources, metrics, fallback, message_saved, [DONE]
```

**OpenCodeBackend:** Delegates to `agent_loop.stream_agent_loop()`. The built-in agent.

**HermesBackend:** HTTP/SSE proxy to external Hermes service. Falls back to OpenCode if unhealthy.

## src/tool_index.py — RAG-Based Tool Selection (476 lines)

**Purpose:** Instead of injecting all 60+ tool descriptions into every prompt, embed them in ChromaDB and retrieve only the top-K relevant tools per user message.

**ChromaDB collection:** `odysseus_tool_index`

**ALWAYS_AVAILABLE tools** (never excluded by retrieval):
```python
{"bash", "python", "web_search", "web_fetch", "read_file", "api_call",
 "list_served_models", "stop_served_model", "app_api"}
```

**ASSISTANT_ALWAYS_AVAILABLE** (for scheduled tasks/check-ins):
```python
{"list_email_accounts", "list_emails", "read_email", "send_email", "reply_to_email",
 "bulk_email", "archive_email", "delete_email", "mark_email_read",
 "manage_calendar", "manage_notes", "manage_tasks",
 "manage_memory", "web_search", "read_file",
 "create_document", "update_document",
 "resolve_contact", "search_chats", "api_call", "ui_control"}
```

**Tool descriptions:** Rich, searchable descriptions in `BUILTIN_TOOL_DESCRIPTIONS` dict — each tool gets a paragraph explaining when to use it, what it does, and common pitfalls.

## src/task_scheduler.py — Background Task Scheduler (2202 lines)

**Purpose:** Cron-based scheduled task execution with timezone support.

**Shared TTL cache (singleflight):**
- `_shared_cache` dict with TTL expiry
- `_shared_cache_pending` for in-flight deduplication
- Multiple tasks firing same minute share one fetch call
- Exceptions propagate to all waiters without poisoning cache

**compute_next_run():** Supports schedule types: `cron`, `once`, `daily`, `weekly`, `hourly`, `interval`
- Timezone-aware via `zoneinfo.ZoneInfo`
- Cron expressions via `croniter` library
- All times stored as naive UTC in DB

**HOUSEKEEPING_DEFAULTS:** Built-in tasks for system maintenance.

## src/deep_research.py — Deep Research Engine (830 lines)

**Purpose:** IterResearch-style autonomous research with LLM-in-the-loop.

**Research loop:** Think → Search → Extract → Synthesize

**Prompt chain:**
1. `RESEARCH_PLAN_PROMPT` — Analyze question, create sub-questions and key topics
2. `QUERY_GEN_PROMPT` — Generate focused search queries for current round
3. `SYNTHESIZE_PROMPT` — Integrate new findings into evolving report
4. `STOP_PROMPT` — LLM decides if research is comprehensive enough
5. `FINAL_REPORT_PROMPT` — Generate magazine-quality 1500+ word report

**Category-specific formats:**
- `product` — Ranked list with pros/cons, price, comparison table
- `comparison` — Comparison table + per-option sections + verdicts
- `howto` — Quick guide + prerequisites + detailed steps + common mistakes

**Configuration:**
- `research_max_tokens: 16384`
- `research_extraction_timeout_seconds: 90`
- `research_extraction_concurrency: 3`
- `research_run_timeout_seconds: 1800` (30 min hard cap)

---

# 4. FRONTEND SYSTEM ARCHITECTURE

## SPA Architecture

Odysseus uses a **single-page application** architecture with NO build step. All JavaScript is vanilla ES modules loaded directly by the browser.

**Entry point:** `static/index.html` (189KB) — contains all panel HTML structure.
**Core JS:** `static/app.js` (172KB) — router, state management, initialization.
**Styling:** `static/style.css` (1084KB) — complete CSS with theme system.

## Routing

Client-side routing via `app.js`. URL paths map to panel visibility:
- `/` — Chat panel (default)
- `/notes` — Notes panel
- `/calendar` — Calendar panel
- `/cookbook` — Cookbook (model management)
- `/email` — Email panel
- `/memory` — Memory/Brain panel
- `/gallery` — Gallery panel
- `/tasks` — Tasks panel
- `/library` — Library (documents + research)

All SPA routes are served the same `index.html` by FastAPI fallback.

## JS Module Architecture (73 modules in static/js/)

### Core modules:
| Module | Size | Purpose |
|--------|------|---------|
| `app.js` | 172KB | Router, state, initialization, global event handlers |
| `init.js` | 15KB | Startup sequence, feature detection |
| `ui.js` | 49KB | UI utilities, DOM helpers, panel management |
| `storage.js` | 3KB | localStorage wrapper |
| `platform.js` | 2KB | OS/browser detection |

### Feature modules:
| Module | Size | Purpose |
|--------|------|---------|
| `chat.js` | 215KB | Chat interface, message sending, SSE streaming |
| `chatRenderer.js` | 103KB | Message rendering, markdown, code blocks |
| `chatStream.js` | 12KB | SSE stream parsing for chat |
| `document.js` | 413KB | Document editor, code highlighting, versioning |
| `documentLibrary.js` | 177KB | Document list, search, management |
| `sessions.js` | 125KB | Session list, switching, creation, organization |
| `settings.js` | 219KB | Settings panel, all configuration options |
| `notes.js` | 227KB | Notes/checklists CRUD, drag-sort, reminders |
| `emailLibrary.js` | 227KB | Email inbox, compose, read, multi-account |
| `emailInbox.js` | 52KB | Email inbox view |
| `calendar.js` | 156KB | Calendar view, CalDAV sync, event CRUD |
| `gallery.js` | 134KB | Gallery grid, albums, image viewing |
| `galleryEditor.js` | 157KB | Image editing, AI upscale/inpaint/rembg |
| `cookbook.js` | 101KB | Model management main view |
| `cookbookServe.js` | 114KB | Model serving configuration |
| `cookbookRunning.js` | 141KB | Active model server monitoring |
| `cookbook-hwfit.js` | 80KB | Hardware compatibility checking |
| `cookbook-diagnosis.js` | 31KB | Serve failure diagnosis |
| `cookbookDownload.js` | 21KB | HuggingFace model downloads |
| `tasks.js` | 124KB | Scheduled task management |
| `memory.js` | 50KB | Memory/brain panel |
| `skills.js` | 89KB | Skills management |
| `admin.js` | 107KB | Admin panel (users, endpoints, system) |

### UI utility modules:
| Module | Size | Purpose |
|--------|------|---------|
| `theme.js` | 104KB | Theme system, CSS variable management |
| `markdown.js` | 32KB | Markdown rendering (marked.js wrapper) |
| `modalManager.js` | 67KB | Modal dialog system |
| `modalSnap.js` | 33KB | Modal positioning/snapping |
| `modelPicker.js` | 29KB | Model selection dropdown |
| `slashCommands.js` | 255KB | Slash command system (/search, /research, etc.) |
| `sidebar-layout.js` | 26KB | Sidebar panel layout management |
| `keyboard-shortcuts.js` | 12KB | Global keyboard shortcuts |
| `spinner.js` | 12KB | Loading spinners |
| `dragSort.js` | 8KB | Drag-and-drop sorting |

### Specialized modules:
| Module | Size | Purpose |
|--------|------|---------|
| `assistant.js` | 21KB | Personal assistant features |
| `agentSelector.js` | 4KB | Agent backend switching |
| `codeRunner.js` | 13KB | In-browser code execution |
| `colorPicker.js` | 16KB | Color selection |
| `censor.js` | 13KB | Content censoring |
| `voiceRecorder.js` | 8KB | Microphone recording for STT |
| `tts-ai.js` | 18KB | TTS playback |
| `a11y.js` | 7KB | Accessibility features |
| `signature.js` | 18KB | Email signature editor |
| `presets.js` | 44KB | Chat preset management |
| `providers.js` | 13KB | Provider configuration |
| `rag.js` | 5KB | RAG mode toggle |
| `group.js` | 40KB | Session grouping |

### Editor subsystem (static/js/editor/ — 34 files):
Full code editor implementation with language support, syntax highlighting, autocomplete, and editing operations.

### Compare subsystem (static/js/compare/ — 10 files):
Model comparison interface for side-by-side response evaluation.

### Calendar subsystem (static/js/calendar/ — 2 files):
Calendar view components.

### Research subsystem (static/js/research/ — 2 files):
Deep research progress and results display.

### Email subsystem (static/js/emailLibrary/ — 4 files):
Email composition and management components.

## CSS Architecture (style.css — 1084KB)

Single monolithic CSS file with:
- **CSS custom properties** for theming (colors, fonts, spacing)
- **Theme system** via `theme.js` — creates/modifies themes by setting CSS variables
- **Responsive design** — mobile-first with breakpoints
- **Component-scoped** selectors (panel-based organization)
- **Dark/light mode** support
- **Font system** — `/static/fonts/` with custom web fonts

## Frontend-Backend Communication

- **REST API** — Standard JSON request/response for CRUD operations
- **SSE (Server-Sent Events)** — Streaming for chat, agent, shell output
- **No WebSocket** — All real-time communication uses SSE (simpler, HTTP-compatible)
- **Polling** — Email pollers, calendar sync use periodic polling
- **File uploads** — multipart/form-data via `/api/upload`

---

# 5. BACKEND SYSTEM ARCHITECTURE

## FastAPI Application Structure

```
app.py (FastAPI instance)
├── Middleware Chain
│   ├── CORSMiddleware
│   ├── SecurityHeadersMiddleware
│   ├── RequestTimeoutMiddleware (45s default)
│   └── AuthMiddleware (cookie + bearer + internal)
├── Static Files (StaticFiles mount)
├── Route Modules (47 APIRouter instances)
├── Startup Event (lifecycle hooks)
└── Shutdown Event (cleanup hooks)
```

## Route Registration Pattern

Each route module exports `setup_*_routes() -> APIRouter`:
```python
router = APIRouter(tags=["feature_name"])
# ... define endpoints ...
return router
```

In `app.py`:
```python
from routes.chat_routes import setup_chat_routes
app.include_router(setup_chat_routes())
```

## Middleware Details

### CORSMiddleware
- Origins: `ALLOWED_ORIGINS` env var (comma-separated)
- Credentials: True
- Methods: GET, POST, PUT, DELETE
- Headers: Accept, Authorization, Content-Type, X-API-Key, X-Auth-Token, X-Odysseus-Internal-Token, X-Odysseus-Owner, X-Requested-With, X-TZ-Offset

### SecurityHeadersMiddleware
- Per-request CSP nonce (`secrets.token_hex(16)`)
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: no-referrer`
- `X-Frame-Options: DENY` (except tool renders and reports)
- CSP: `default-src 'self'; script-src 'self' 'nonce-{nonce}'`
- Research reports get relaxed CSP for external images
- Tool iframe renders skip framing headers

### RequestTimeoutMiddleware
- Default: 45 seconds
- Exempt paths: streaming endpoints, research, uploads
- Uses asyncio.wait_for with timeout

### AuthMiddleware
- Cookie-based session auth (primary)
- Bearer token auth (`ody_` prefix for API tokens)
- Internal-tool token bypass (in-process loopback)
- LOCALHOST_BYPASS for development
- Sets `request.state.current_user` on success

## Key API Endpoints

### Chat System
- `POST /api/chat` — Non-streaming chat completion
- `POST /api/chat_stream` — Streaming chat with SSE
- `POST /api/inject_context` — Inject context into session
- `POST /api/search` — Search within chat history

### Agent System
- `GET /api/agents` — List agent backends
- `GET /api/agents/current` — Current active backend
- `POST /api/agents/switch` — Switch backend

### Session Management
- `GET /api/sessions` — List sessions (owner-filtered)
- `POST /api/sessions` — Create session
- `GET /api/sessions/{id}` — Get session with messages
- `DELETE /api/sessions/{id}` — Delete session
- `PUT /api/sessions/{id}/archive` — Archive
- `POST /api/sessions/{id}/fork` — Fork session

### Documents
- `GET /api/documents` — List documents
- `POST /api/documents` — Create document
- `PUT /api/documents/{id}` — Update document
- `DELETE /api/documents/{id}` — Delete

### Research
- `POST /api/research/start` — Start deep research
- `GET /api/research/status/{id}` — Research status
- `GET /api/research/results` — List results

### Email
- `GET /api/email/accounts` — List accounts
- `POST /api/email/accounts` — Add account
- `GET /api/email/list` — List emails
- `POST /api/email/send` — Send email
- `POST /api/email/reply` — Reply to email

### Calendar
- `GET /api/calendar/events` — List events
- `POST /api/calendar/events` — Create event
- `PUT /api/calendar/events/{uid}` — Update
- `DELETE /api/calendar/events/{uid}` — Delete

### Models
- `GET /api/models` — List available models
- `POST /api/models/endpoints` — Add endpoint
- `DELETE /api/models/endpoints/{id}` — Remove

### Tasks
- `GET /api/tasks` — List scheduled tasks
- `POST /api/tasks` — Create task
- `PUT /api/tasks/{id}` — Update
- `POST /api/tasks/{id}/run` — Run now

### Shell
- `POST /api/shell/execute` — Run command
- `POST /api/shell/stream` — Stream command output

### TTS/STT
- `POST /api/tts/synthesize` — Text to speech
- `POST /api/stt/transcribe` — Speech to text

## Service Layer Architecture

Services are independent modules with clean interfaces:

```
routes/ → src/ (business logic) → services/ (capabilities) → external APIs
```

### Search Service
- **Core:** `services/search/core.py` — orchestrator with provider chain
- **Providers:** 6 implementations with fallback
- **Cache:** File-based search result cache
- **Analytics:** Error tracking, rate limit detection
- **Content:** Web page extraction (BeautifulSoup)

### Memory Service
- **Storage:** JSON file (`data/memory.json`)
- **Similarity:** Jaccard coefficient for text matching
- **Vector:** ChromaDB for semantic search
- **Extractor:** LLM-driven memory extraction
- **Skills:** SKILL.md file system with usage tracking

### Shell Service
- **Execution:** `asyncio.create_subprocess_shell`
- **Timeout:** Configurable per command
- **Streaming:** Line-by-line output streaming
- **Max output:** 200KB limit

### TTS Service
- **Providers:** disabled, browser (Web Speech), local (Kokoro-82M), endpoint (OpenAI API)
- **Cache:** SHA-256 keyed file cache in `data/tts_cache/`
- **Format detection:** MP3 vs WAV by magic bytes

### STT Service
- **Providers:** disabled, browser, local (faster-whisper), endpoint
- **CUDA detection:** Tries torch.cuda, falls back to CPU
- **Compute type:** float16 on GPU, int8 on CPU

### Hardware Detection (hwfit)
- **NVIDIA:** nvidia-smi with SSH remote fallback
- **AMD:** rocm-smi detection
- **Apple:** system_profiler for Metal GPUs
- **GPU grouping:** Homogeneous pools for tensor parallel
- **Cache TTL:** 30 minutes (hardware rarely changes)

## Startup Lifecycle

```
1. MIME type registration
2. Windows symlink workaround
3. Load .env
4. Create FastAPI app
5. Add CORS middleware
6. Add security headers middleware
7. Add request timeout middleware
8. Add auth middleware
9. Mount static files
10. Initialize managers (memory, skills, sessions, presets, etc.)
11. Register all route modules
12. @app.on_event("startup"):
    a. Start agent manager
    b. Purge incognito sessions
    c. Schedule upload cleanup
    d. Start background monitor
    e. Connect MCP servers
    f. Warm tool index (ChromaDB)
    g. Warm LLM endpoints + keepalive
    h. Create default scheduled tasks
    i. Backfill skill owners
    j. Start task scheduler
    k. Sweep null-owner sessions
    l. Schedule nightly skill audit
```

## Shutdown Lifecycle

```
1. Stop agent manager
2. Cancel upload cleanup
3. Stop task scheduler
4. Close webhook manager
5. Disconnect MCP servers
```

---

# 6. AI SYSTEM ARCHITECTURE

## Model Abstraction Layer

The AI system is built on a **provider-agnostic abstraction layer** in `src/llm_core.py`. All LLM communication flows through two primary functions:

### `llm_call()` / `llm_call_async()` — Non-streaming
- Synchronous and async variants
- Used for utility calls (memory extraction, research planning, summarization)
- Response cache (128 entries, SHA-256 keyed)
- Dead-host cooldown (20s after 2 consecutive failures)

### `stream_llm()` — Streaming
- Yields SSE-formatted strings
- Provider-specific format conversion
- Thinking token preservation
- Tool call parsing (Anthropic tool_use, Ollama tool_calls, OpenAI function_call)

### `stream_llm_with_fallback()` — Streaming with failover
- Takes ordered list of (url, model, headers) candidates
- Pre-content failure → automatically try next candidate
- Post-content failure → surface to user (model already started responding)

## Provider Handling

### Provider Detection (URL-based)
```python
def _detect_provider(url: str) -> str:
    hostname = urlparse(url).hostname or ""
    if "anthropic" in hostname:
        return "anthropic"
    if "ollama" in hostname or ":11434" in url:
        return "ollama"
    if "openrouter" in hostname:
        return "openrouter"
    if "groq" in hostname:
        return "groq"
    return "openai"  # Default: OpenAI-compatible
```

### Anthropic Integration
- **Native API:** `POST /v1/messages` (not OpenAI-compatible)
- **Auth:** `x-api-key` header (not Bearer token)
- **Format:** Messages converted to Anthropic format (system separate, tool_use/tool_result content blocks)
- **Prompt caching:** `cache_control: {"type": "ephemeral"}` on system prompts and tool schemas
- **Headers:** `anthropic-version: 2023-06-01`

### Ollama Integration
- **Native API:** `POST /api/chat` (not OpenAI-compatible)
- **No auth required** (local service)
- **Tool calls normalization:** String arguments → parsed JSON objects
- **Thinking tokens:** Extracted and surfaced separately

### OpenRouter Integration
- **OpenAI-compatible format** with extra headers
- **HTTP-Referer:** Set to app URL
- **X-Title:** "Odysseus UI"

### Groq Integration
- **OpenAI-compatible format**
- Standard API key auth

### OpenAI-Compatible (Default)
- Works with: OpenAI, xAI/Grok, Mistral, DeepSeek, Google, Together, Fireworks, local vLLM/SGLang
- `stream_options: {"include_usage": True}` for token counting
- `max_completion_tokens` for reasoning models (o1, o3, o4, gpt-4.5, gpt-5)

## Endpoint Resolution (`src/endpoint_resolver.py`)

**Unified resolution** consolidates 4+ copies of normalize/resolve logic:

1. **Tailscale resolution:** If DNS fails, try `tailscale status --json` to find host IP
2. **Provider-specific URL builders:**
   - Anthropic → `/v1/messages`
   - Ollama → `/api/chat`
   - OpenAI → `/v1/chat/completions` (via `build_chat_url()`)
3. **resolve_endpoint():** Settings-based resolution with fallback chain
   - Check `default_endpoint_id` setting
   - Check utility endpoint for utility calls
   - Fall back to first enabled endpoint
4. **Hidden model filtering:** Models disabled in UI are excluded from auto-pick
5. **First-chat-model:** Skips embedding/TTS models when auto-picking

**Fallback candidate chains:**
- Chat: configured model → utility model → first available
- Utility: configured utility endpoint → chat endpoint
- Vision: configured vision model → vision fallbacks list

## Model Discovery (`src/model_discovery.py`)

**Tailscale host discovery:** `tailscale status --json` → extract all peer hostnames
**Port scanning:** 8000-8020 + 11434 across all discovered hosts
**ThreadPoolExecutor:** 50 workers for parallel scanning
**Built-in providers:**
- OpenAI: GPT-5.2, GPT-4o (if OPENAI_API_KEY set)
- xAI: Grok-4.3, Grok-4 (if XAI_API_KEY set)

## API Key Management

- **Environment variables:** OPENAI_API_KEY, XAI_API_KEY at startup
- **API Key Manager:** `src/api_key_manager.py` — persisted in `data/api_keys.json`
- **Brave Search:** Stored in settings.json
- **ModelEndpoint API keys:** Encrypted in database (EncryptedText)
- **Email passwords:** Encrypted in database
- **Integration credentials:** Encrypted via `src.secret_storage` (Fernet)
- **App key:** `data/.app_key` — Fernet key generated on first boot

## Provider Failover

### Dead-Host Cooldown
```
Host fails → increment _host_fails counter
If counter >= 2 → mark host dead for 20s
Any success → reset counter, clear dead status
Dead host → immediate 503 without connection attempt
```

### Model Fallback Chains
- Configured in settings for chat, utility, vision categories
- `stream_llm_with_fallback()` tries each candidate in order
- Pre-content failure (connection error, auth error) → next candidate
- Post-content failure (mid-stream error) → surface error

### Search Provider Fallback
- Primary provider (configurable: searxng, brave, duckduckgo, google_pse, tavily, serper)
- Fallback chain from settings or default `["duckduckgo"]`
- Each provider tried in order until results found

## Inference Flow

### Chat Flow (Non-Agent)
```
User message → chat_routes.py → ChatHandler.preprocess_message()
  → Extract URLs, YouTube transcripts, image attachments
  → Build user content (documents, RAG context)
  → chat_processor.build_context() → memory injection, personal docs
  → stream_llm() or stream_llm_with_fallback()
  → Stream SSE to client
  → Save assistant response to DB
  → Run post-response tasks (memory extraction)
```

### Agent Flow
```
User message → chat_routes.py → Check chat_mode == "agent"
  → agent_manager.get_active_backend()
  → backend.stream() → OpenCodeBackend delegates to agent_loop
  → stream_agent_loop():
    1. Build system prompt (preamble + rules + tool descriptions)
    2. tool_index.get_relevant_tools(user_message) → RAG retrieval
    3. Inject tool schemas (function calling) or descriptions (code block mode)
    4. stream_llm() with tools parameter
    5. Parse tool calls (function_call or code blocks)
    6. Execute tools via execute_tool_block()
    7. Format results, append to messages
    8. Loop back to step 4 (until no more tools or max rounds)
  → Stream SSE to client
  → Save final response
```

### Research Flow
```
User triggers research → research_routes.py → deep_research.py
  1. RESEARCH_PLAN_PROMPT → LLM creates sub-questions
  2. Loop (max rounds):
     a. QUERY_GEN_PROMPT → LLM generates search queries
     b. Execute searches via search service (parallel)
     c. Extract content from result URLs (parallel)
     d. EXTRACTOR_PROMPT → LLM extracts relevant info
     e. SYNTHESIZE_PROMPT → LLM updates report
     f. STOP_PROMPT → LLM decides if complete
  3. FINAL_REPORT_PROMPT → Generate comprehensive report
  4. Save to data/deep_research/
  5. Return report + sources
```

## Streaming Systems

All streaming uses **Server-Sent Events (SSE)**:
- `Content-Type: text/event-stream`
- `Cache-Control: no-cache`
- `Connection: keep-alive`

Event format: `data: {JSON}\n\n`
Terminal event: `data: [DONE]\n\n`

### Stream Types:
1. **Chat stream** — delta text, thinking tokens, usage metrics
2. **Agent stream** — delta + tool_start + tool_output + agent_step + web_sources + metrics
3. **Shell stream** — stdout/stderr lines + exit_code
4. **Research stream** — progress updates (round, queries, sources found)

## Context Handling

### Context Building (`src/chat_processor.py`)
1. System prompt (preset or default)
2. Memory injection (relevant memories by Jaccard similarity)
3. Personal docs RAG context (if session has RAG enabled)
4. Skills injection (relevant skills by keyword matching)
5. Chat history (last N messages, configurable MAX_CONTEXT_MESSAGES=90)
6. Current message with attachments

### Token Estimation (`src/model_context.py`)
- `estimate_tokens()` — approximate token count for context management
- Used to decide when to compact history

### Context Compaction (`src/context_compactor.py`)
- When history exceeds budget, older messages summarized
- Summaries replace original messages in context

## Memory Systems

### JSON Memory (`src/memory.py` + `services/memory/memory.py`)
- Storage: `data/memory.json`
- Categories: fact, event, contact, preference, task
- Inline commands: "remember: X" → direct memory creation
- Jaccard similarity for relevance scoring
- Owner-scoped entries

### Vector Memory (`services/memory/memory_vector.py`)
- ChromaDB collection for semantic search
- Embeddings via HTTP API or fastembed
- Rebuilt from JSON memory on startup if empty
- Used for memory retrieval in chat context

### Memory Extraction (`services/memory/memory_extractor.py`)
- LLM-driven extraction from conversations
- Identifies facts, preferences, contacts, tasks
- Runs as post-response task

## Embeddings/Vector Systems

### Embedding Client (`src/embeddings.py`)
- **Priority:** HTTP API (Ollama/vLLM `/v1/embeddings`)
- **Fallback:** Local fastembed (ONNX, ~50MB model)
- **Connect timeout:** 3 seconds for fast fallback
- **Model:** `sentence-transformers/all-MiniLM-L6-v2` default

### ChromaDB Integration
- **Host:** Configurable (Docker: `chromadb:8000`, local: `localhost:8100`)
- **Collections:**
  - `odysseus_tool_index` — Tool description embeddings for RAG selection
  - Memory vectors — Semantic memory search
  - Document RAG — Personal document retrieval
- **Client:** `chromadb-client` (lightweight HTTP client)

---

# 7. AGENT SYSTEM ANALYSIS

## Agent Architecture

```
AgentManager (singleton, thread-safe)
├── OpenCodeBackend (built-in)
│   └── agent_loop.stream_agent_loop()
│       ├── llm_core.stream_llm() / stream_llm_with_fallback()
│       ├── tool_index.get_relevant_tools() → ChromaDB RAG
│       ├── tool_schemas.FUNCTION_TOOL_SCHEMAS → OpenAI function format
│       ├── agent_tools.parse_tool_blocks() / execute_tool_block()
│       └── tool_implementations → 60+ tool implementations
├── HermesBackend (external)
│   └── HTTP/SSE proxy to Hermes service
│       └── Falls back to OpenCode if unhealthy
└── LeadHunterBackend (NEW)
    └── Specialized lead discovery agent
        ├── discover_producthunt_leads / discover_beta_leads
        ├── score_leads → qual scoring pipeline
        ├── sync_to_listmonk → campaign import
        └── campaign_metrics / export_leads
```

## Agent Backend Selection

1. `AGENT_BACKEND` env var → initial default
2. `settings.json` → `agent_backend` field → persisted choice
3. `/api/agents/switch` API → runtime switching
4. Health check → falls back to OpenCode if selected backend unhealthy

## Skills System

### Skill Storage (`services/memory/skills.py`)
- **Location:** `data/skills/<category>/<name>/SKILL.md`
- **Format:** YAML frontmatter + structured markdown body
- **Sections:** When to Use, Procedure, Pitfalls, Verification
- **Ownership:** `owner: <username>` in frontmatter
- **Usage tracking:** `data/skills/_usage.json` sidecar (uses count, last_used)

### Skill Format (`services/memory/skill_format.py`)
```yaml
---
name: skill-name
category: general
owner: username
confidence: 0.9
tags: [tag1, tag2]
---

## When to Use
Description of when this skill applies

## Procedure
Step-by-step instructions

## Pitfalls
Common mistakes to avoid

## Verification
How to verify the skill was applied correctly
```

### Skill Lifecycle
1. **Creation:** Agent extracts skill from successful interaction
2. **Storage:** Written as SKILL.md with frontmatter
3. **Retrieval:** Keyword + Jaccard matching against user messages
4. **Injection:** Relevant skills added to system prompt
5. **Usage tracking:** Counter incremented on each retrieval

## Tools System

### Tool Categories (60+ tools)

**Shell/Code:**
- `bash` — Shell command execution (full access)
- `python` — Python code execution
- `read_file` / `write_file` — File I/O

**Web:**
- `web_search` — Quick web lookup
- `web_fetch` — Fetch specific URL content
- `trigger_research` — Start deep research job

**Document:**
- `create_document` — Create editor document
- `edit_document` — Find/replace edits (preferred)
- `update_document` — Full document rewrite
- `suggest_document` — Code review suggestions
- `manage_documents` — List/read/delete documents

**Communication:**
- `list_email_accounts` / `list_emails` / `read_email`
- `send_email` / `reply_to_email` / `bulk_email`
- `archive_email` / `delete_email` / `mark_email_read`
- `resolve_contact` / `manage_contact`

**Productivity:**
- `manage_calendar` — CalDAV event CRUD
- `manage_notes` — Notes/checklists with reminders
- `manage_tasks` — Scheduled task management
- `manage_memory` — Persistent memories
- `manage_session` / `list_sessions` / `create_session` / `send_to_session` / `search_chats`

**Model Management (Cookbook):**
- `download_model` — HuggingFace model download
- `serve_model` — Start model server (vLLM, SGLang, llama.cpp, Ollama)
- `list_served_models` / `stop_served_model`
- `list_downloads` / `cancel_download`
- `search_hf_models` — Search HuggingFace
- `list_cached_models` / `list_serve_presets` / `serve_preset`
- `adopt_served_model` / `list_cookbook_servers`

**System:**
- `manage_endpoints` — LLM endpoint management
- `manage_mcp` — MCP server management
- `manage_webhooks` — Webhook management
- `manage_tokens` — API token management
- `manage_settings` — App settings changes
- `ui_control` — UI toggles, panel opening, theme switching
- `app_api` — Generic loopback to any API endpoint
- `chat_with_model` / `ask_teacher` / `pipeline` — Multi-model operations
- `generate_image` / `edit_image` — Image generation/editing

### Tool Selection (RAG-Based)
1. All tool descriptions embedded in ChromaDB collection
2. User message embedded using same model
3. Top-K most similar tools retrieved
4. ALWAYS_AVAILABLE tools added unconditionally
5. ASSISTANT_ALWAYS_AVAILABLE tools added for scheduled tasks
6. Final tool set injected into system prompt / function schemas

### Tool Execution
1. **Code block mode:** LLM writes fenced code block with tool name as language
2. **Function call mode:** LLM uses native function calling (Anthropic, Ollama, OpenAI)
3. `parse_tool_blocks()` — Extract tool calls from response
4. `execute_tool_block()` — Dispatch to tool implementation
5. `format_tool_result()` — Format output for LLM consumption
6. Result appended to message history for next round

### Tool Security (`src/tool_security.py`)
- `blocked_tools_for_owner()` — Per-user tool restrictions
- Privilege checks (can_use_bash, can_use_agent, etc.)
- MCP disabled tools per server

## Task Execution

### Scheduled Tasks (`src/task_scheduler.py`)
- **Cron expressions** via croniter library
- **Timezone support** via zoneinfo
- **Schedule types:** cron, once, daily, weekly, hourly, interval
- **Shared TTL cache** (singleflight) for data fetch deduplication
- **Actions:** Send prompt to LLM, run script, fire event

### Autonomous Workflows
1. Task fires at scheduled time
2. Prompt sent to configured task model
3. Agent executes with ASSISTANT_ALWAYS_AVAILABLE tools
4. Results stored, notifications sent (browser/email/ntfy)

## MCP Integration

### MCP Manager (`src/mcp_manager.py`)
- **Transport:** stdio (subprocess) + SSE (HTTP)
- **Connection lifecycle:** connect → list_tools → call_tool → disconnect
- **Per-server disabled tools** stored in database
- **Auto-reconnection** on failure

### Built-in MCP Servers
- `email_server.py` — Full email (IMAP/SMTP)
- `memory_server.py` — Memory management
- `image_gen_server.py` — Image generation
- `rag_server.py` — RAG index management

---

# 8. DATABASE / STORAGE / MEMORY

## Database Engine

- **Default:** SQLite (`sqlite:///./data/app.db`)
- **Configurable:** `DATABASE_URL` env var (supports PostgreSQL, etc.)
- **ORM:** SQLAlchemy with declarative base
- **Session factory:** `SessionLocal` with autocommit=False, autoflush=False
- **Thread safety:** `check_same_thread=False` for SQLite

## Persistence Systems

### SQLite Database (20+ tables)
All structured data: sessions, messages, documents, endpoints, accounts, tasks, etc.

### JSON Files
- `data/auth.json` — User accounts and configuration
- `data/sessions.json` — Session metadata cache (lazy hydration)
- `data/memory.json` — Memory entries
- `data/settings.json` — Application settings
- `data/features.json` — Feature flags
- `data/presets.json` — Chat presets
- `data/integrations.json` — API integration configs
- `data/cookbook_state.json` — Cookbook state
- `data/user_prefs.json` — User preferences
- `data/skills/_usage.json` — Skill usage counters

### Encrypted Storage
- **Fernet encryption** via `src.secret_storage`
- **Key:** `data/.app_key` (generated on first boot)
- **Encrypted columns:** EmailAccount passwords, ModelEndpoint API keys, Signatures
- **Pattern:** `EncryptedText` TypeDecorator — transparent encrypt/decrypt

### Atomic I/O (`core/atomic_io.py`)
- Write to temp file → `fsync()` → `os.replace()` → atomic swap
- Prevents corruption on crash/power loss
- Used for all JSON config files

## Vector Storage (ChromaDB)

- **Service:** Separate Docker container (`chromadb:8000`)
- **Client:** `chromadb-client` HTTP client
- **Collections:**
  - Tool index (RAG tool selection)
  - Memory vectors (semantic search)
  - Document RAG (personal document retrieval)
- **Embeddings:** HTTP API (Ollama) or local fastembed (ONNX)

## Caching Systems

### Response Cache (`llm_core.py`)
- 128 entries max
- SHA-256 key from request parameters
- In-memory, process-local

### Search Cache (`services/search/cache.py`)
- File-based in `data/search_cache/`
- Duration varies by query type
- Key: hash of query + count + time_filter

### TTS Cache (`data/tts_cache/`)
- SHA-256 key from text + provider + model + voice + speed
- MP3 or WAV format (detected by magic bytes)

### Settings Cache (`src/settings.py`)
- 2-second TTL
- Avoids JSON re-parsing on hot paths

### TTL Cache (`task_scheduler.py`)
- Singleflight pattern for shared data fetches
- Configurable TTL per cache key
- In-flight deduplication

### Hardware Cache (`services/hwfit/hardware.py`)
- 30-minute TTL
- Hardware info rarely changes

## Session Handling

### Session Lifecycle
1. **Creation:** UUID generated, metadata written to DB + JSON
2. **Lazy hydration:** Messages loaded on first access
3. **Message persistence:** Each message saved to DB with timestamp
4. **Auto-archive:** Old sessions archived based on age
5. **Cleanup:** Empty sessions deleted periodically

### Session Modes
- **Chat mode:** Direct LLM conversation
- **Agent mode:** Tool-augmented conversation
- Stored per-session in database

---

# 9. DOCKER + INFRASTRUCTURE ANALYSIS

## Docker Compose Architecture (4 services)

### Service: odysseus
- **Port:** 7000 (configurable via APP_PORT)
- **Bind:** 0.0.0.0 (configurable via APP_BIND)
- **Build:** From Dockerfile (Python 3.12-slim)
- **Depends on:** searxng (healthy), chromadb (started)
- **Restart:** unless-stopped
- **Volumes:**
  - `./data:/app/data` — All persistent data
  - `./logs:/app/logs` — Log files
  - `./data/ssh:/app/.ssh` — SSH keys for Cookbook
  - `./data/huggingface:/app/.cache/huggingface` — HF model cache
  - `./data/local:/app/.local` — Installed Python CLIs
- **Extra hosts:** `host.docker.internal:host-gateway` (reach host Ollama)
- **PUID/PGID:** Drop privileges to host user (entrypoint.sh)

### Service: chromadb
- **Image:** `chromadb/chroma:latest`
- **Port:** 8100 → 8000 (configurable bind)
- **Volume:** `chromadb-data:/chroma/chroma`
- **Telemetry:** Disabled (ANONYMIZED_TELEMETRY=FALSE)
- **Restart:** unless-stopped

### Service: searxng
- **Image:** `searxng/searxng:latest`
- **Port:** 8080
- **Custom entrypoint:** Secret injection into settings template
- **Volumes:**
  - `searxng-data:/etc/searxng` — Persistent config
  - `./config/searxng/settings.yml` — Template (read-only)
- **Capabilities:** CHOWN, SETGID, SETUID, DAC_OVERRIDE (for first-boot setup)
- **Healthcheck:** Python urllib probe every 5s, 20 retries, 10s start period
- **Restart:** unless-stopped

### Service: ntfy
- **Image:** `binwiederhier/ntfy`
- **Command:** serve
- **Port:** 8091 → 80 (configurable bind)
- **Volume:** `ntfy-cache:/var/cache/ntfy`
- **Restart:** unless-stopped

## Dockerfile (48 lines)
```
Base: python:3.12-slim
System deps: build-essential, cmake, curl, git, nodejs, npm, tmux, openssh-client, gosu
Python deps: requirements.txt
Workdir: /app
Copy: entire project
Entrypoint: docker/entrypoint.sh
CMD: uvicorn app:app --host 0.0.0.0 --port 7000
```

## Entrypoint (`docker/entrypoint.sh`, 87 lines)
1. Read PUID/PGID from environment
2. Create odysseus user/group with matching IDs
3. chown /app/data + /app/logs to odysseus user
4. Auto-detect CUDA_HOME for GPU support
5. Disable FlashInfer sampler if incompatible
6. `exec gosu odysseus "$@"` — drop privileges and run CMD

## GPU Support
- **NVIDIA:** `docker/gpu.nvidia.yml` overlay (nvidia-container-toolkit)
- **AMD:** `docker/gpu.amd.yml` overlay (ROCm + RENDER_GID)
- **Selection:** `COMPOSE_FILE=docker-compose.yml:docker/gpu.nvidia.yml`

## Networking
- **odysseus → chromadb:** Docker internal network (chromadb:8000)
- **odysseus → searxng:** Docker internal network (searxng:8080)
- **odysseus → host:** `host.docker.internal` for Ollama
- **odysseus → internet:** Direct for API calls (OpenAI, OpenRouter, etc.)
- **Browser → odysseus:** localhost:7000 (or LAN IP if APP_BIND=0.0.0.0)

## Volumes
- `searxng-data` — SearXNG settings and secret
- `chromadb-data` — ChromaDB vector store
- `ntfy-cache` — ntfy message cache

---

# 10. ENVIRONMENT VARIABLE ANALYSIS

## LLM Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_HOST` | `localhost` | Primary LLM host for model discovery |
| `LLM_HOSTS` | `` | Comma-separated additional LLM hosts |
| `OLLAMA_BASE_URL` | `` | Ollama API URL (e.g., `http://host.docker.internal:11434/v1`) |
| `OPENAI_API_KEY` | `` | OpenAI API key |
| `XAI_API_KEY` | `` | xAI (Grok) API key |
| `RESEARCH_LLM_ENDPOINT` | `` | Research service LLM endpoint URL |
| `HF_TOKEN` / `HUGGING_FACE_HUB_TOKEN` | `` | HuggingFace token for model downloads |

## Search & Web

| Variable | Default | Purpose |
|----------|---------|---------|
| `SEARXNG_INSTANCE` | `http://localhost:8080` | SearXNG instance URL |
| `SEARXNG_SECRET` | `` | SearXNG cookie/CSRF secret |
| `SEARXNG_GENERAL_ENGINES` | `bing,mojeek,presearch` | SearXNG engines for general queries |
| `DATA_BRAVE_API_KEY` | `` | Brave Search API key |
| `GOOGLE_API_KEY` | `` | Google PSE API key |
| `GOOGLE_PSE_CX` | `` | Google PSE custom search engine ID |
| `TAVILY_API_KEY` | `` | Tavily API key |
| `SERPER_API_KEY` | `` | Serper API key |

## Database

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `sqlite:///./data/app.db` | Database connection string |

## Auth & Security

| Variable | Default | Purpose |
|----------|---------|---------|
| `AUTH_ENABLED` | `true` | Enable/disable authentication |
| `LOCALHOST_BYPASS` | `false` | Skip auth for loopback requests (dev only) |
| `SECURE_COOKIES` | `false` | Mark cookies as Secure (HTTPS) |
| `ODYSSEUS_ADMIN_USER` | `admin` | First admin username |
| `ODYSSEUS_ADMIN_PASSWORD` | `` | Pre-seed admin password |
| `ALLOWED_ORIGINS` | `http://localhost,http://127.0.0.1` | CORS allowed origins |

## ChromaDB

| Variable | Default | Purpose |
|----------|---------|---------|
| `CHROMADB_HOST` | `localhost` | ChromaDB service host |
| `CHROMADB_PORT` | `8100` | ChromaDB service port |

## RAG / Embeddings

| Variable | Default | Purpose |
|----------|---------|---------|
| `EMBEDDING_URL` | `http://{LLM_HOST}:11434/v1/embeddings` | Embedding API endpoint |
| `EMBEDDING_MODEL` | `all-minilm:l6-v2` | Embedding model name |
| `FASTEMBED_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local fallback model |
| `FASTEMBED_CACHE_PATH` | `~/.cache/fastembed` | Local model cache path |

## Agent Backend

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENT_BACKEND` | `opencode` | Default agent backend |
| `HERMES_URL` | `` | Hermes service URL |
| `HERMES_API_KEY` | `` | Hermes API key |

## Application

| Variable | Default | Purpose |
|----------|---------|---------|
| `APP_BIND` | `0.0.0.0` | Web UI bind address |
| `APP_PORT` | `7000` | Web UI port |
| `CLEANUP_INTERVAL_HOURS` | `24` | Cleanup interval |
| `ODYSSEUS_INPROCESS_POLLERS` | `1` | Enable in-process email pollers |
| `ODYSSEUS_INPROCESS_TASKS` | `1` | Enable in-process task runner |
| `ODYSSEUS_SCRIPT_HOST` | `localhost` | Host for scheduled scripts |

## Docker-Specific

| Variable | Default | Purpose |
|----------|---------|---------|
| `PUID` | `1000` | Container user ID |
| `PGID` | `1000` | Container group ID |
| `CHROMADB_BIND` | `0.0.0.0` | ChromaDB host bind address |
| `NTFY_BIND` | `0.0.0.0` | ntfy host bind address |
| `NTFY_BASE_URL` | `http://localhost:8091` | ntfy public URL |

## GPU (Docker Compose overlays)

| Variable | Default | Purpose |
|----------|---------|---------|
| `COMPOSE_FILE` | `` | GPU overlay selection (e.g., `docker-compose.yml:docker/gpu.nvidia.yml`) |
| `RENDER_GID` | `` | AMD ROCm render group GID |

---

# 11. API FLOW ANALYSIS

## Request Flow — Chat Stream

```
Browser POST /api/chat_stream
  → CORS: check origin
  → SecurityHeaders: generate CSP nonce
  → RequestTimeout: 45s (exempt for /chat_stream)
  → Auth: validate cookie/bearer/internal-token → set request.state.current_user
  → chat_routes.chat_stream():
    1. Parse ChatRequest (message, session_id, model, attachments, etc.)
    2. _enforce_chat_privileges() — check can_use_agent, can_use_browser, etc.
    3. resolve_session_auth() — verify session ownership
    4. ChatHandler.preprocess_message():
       - Extract URLs from message
       - Check for YouTube URLs → fetch transcript
       - Process image attachments → vision model analysis
       - Build user content (document context, RAG)
    5. Determine chat_mode (chat vs agent)
    6. If agent mode:
       - Get active agent backend
       - Stream via backend.stream() → agent_loop
    7. If chat mode:
       - Build context (memory, skills, personal docs)
       - stream_llm() or stream_llm_with_fallback()
    8. Stream SSE events to browser
    9. Save assistant response to DB
    10. Run post-response tasks (memory extraction, skill extraction)
```

## Request Flow — Session Creation

```
Browser POST /api/sessions
  → Auth middleware
  → session_routes.create_session():
    1. Parse body (name, model, endpoint_url, rag)
    2. Generate UUID
    3. Create Session in DB
    4. Add to sessions.json metadata
    5. Return session object
```

## Request Flow — Agent Tool Execution

```
Agent loop detects tool block in LLM response
  → parse_tool_blocks() — extract tool name + arguments
  → Check tool security (blocked_tools_for_owner)
  → execute_tool_block():
    1. Look up tool implementation
    2. If MCP tool → route to MCP server via mcp_manager
    3. If built-in tool → call tool function
    4. Apply timeout (60s default per tool)
    5. Truncate output (10K char limit)
  → format_tool_result() — format for LLM consumption
  → Append to messages for next round
  → SSE event: tool_start → tool_output
```

## Request Flow — Deep Research

```
Browser POST /api/research/start
  → Auth middleware
  → research_routes.start_research():
    1. Parse topic, session_id
    2. Resolve research endpoint + model
    3. Start background task: deep_research.run_research()
    4. Return job_id immediately
  → Background task:
    1. Create research plan (LLM call)
    2. Loop (Think→Search→Extract→Synthesize):
       a. Generate queries (LLM)
       b. Execute searches (search service, parallel)
       c. Fetch web pages (content service, parallel)
       d. Extract relevant info (LLM per page)
       e. Synthesize report (LLM)
       f. Check completeness (LLM)
    3. Generate final report (LLM)
    4. Save to data/deep_research/{id}.json
    5. Update status to "complete"
```

## Request Flow — Email Operations

```
Browser GET /api/email/list?account=gmail&folder=INBOX
  → Auth middleware
  → email_routes.list_emails():
    1. Resolve account (by name, user, or default)
    2. Connect IMAP (encrypted credentials from DB)
    3. SELECT folder
    4. FETCH headers (UID, subject, from, date, flags)
    5. Check AI summary cache (SQLite: scheduled_emails.db)
    6. Generate summaries for new emails (LLM call)
    7. Return list with summaries
```

## Event Propagation

### Webhook Events
- `session.created` — New chat session
- `chat.completed` — Chat response complete
- `chat.message` — New message
- `webhook.test` — Test event

### Event Bus (`src/event_bus.py`)
- `fire_event()` — Trigger scheduled tasks based on events
- Owner resolution for ownerless events
- Connected to task scheduler for automation

## Async Behavior

- **FastAPI async routes** — Most endpoints are async
- **httpx.AsyncClient** — Shared client for LLM API calls (connection pooling)
- **asyncio.create_subprocess_shell** — Shell command execution
- **ThreadPoolExecutor** — Model discovery port scanning (50 workers)
- **Background tasks** — Research, email polling, scheduled tasks

---

# 12. AUTHENTICATION + SECURITY

## Authentication Systems

### Multi-Path Auth Middleware
1. **Session cookie** (`session_token`): Validate against AuthManager sessions (7-day TTL)
2. **Bearer token** (`Authorization: Bearer ody_...`): Validate against ApiToken DB table
3. **Internal-tool token** (`X-Odysseus-Internal-Token`): Per-process random token for agent loopback
4. **LOCALHOST_BYPASS**: Skip auth for loopback requests (development only)
5. **Auth disabled**: When `AUTH_ENABLED=false`, all requests pass through

### Password Security
- **Algorithm:** bcrypt with auto-generated salt
- **Storage:** `data/auth.json` with atomic writes
- **Verification:** `bcrypt.checkpw()` with UTF-8 encoding

### Session Tokens
- **Generation:** `secrets.token_hex(32)` — 64-character hex string
- **TTL:** 7 days (configurable)
- **Storage:** `data/sessions.json` with thread-safe RLock
- **Revocation:** On logout, password change, or admin action

### TOTP 2FA
- **Library:** pyotp
- **Setup:** Generate secret → show QR code → verify code
- **Backup codes:** Generated during setup, single-use
- **Enforcement:** Checked at login if user has 2FA enabled

### API Tokens
- **Prefix:** `ody_` for identification
- **Storage:** Encrypted in ApiToken DB table
- **Owner attribution:** Each token belongs to a user
- **Management:** Via `/api/tokens` endpoints

## Credential Storage

### Fernet Encryption at Rest
- **Key file:** `data/.app_key` (generated on first boot)
- **Encrypted columns:** EncryptedText TypeDecorator
- **Protected data:** Email passwords, API keys, signatures, integration credentials
- **Limitation:** Protects SQLite file at rest, not live process memory

### Internal Tool Token
- **Purpose:** Let agent tools call admin-gated routes via HTTP loopback
- **Generation:** `secrets.token_hex(32)` at process start
- **Header:** `X-Odysseus-Internal-Token`
- **Security:** Never persisted, never sent externally, per-process only

## Security Measures

### CSP (Content Security Policy)
- Per-request nonce for inline scripts
- `default-src 'self'`
- `script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net`
- `style-src 'self' 'unsafe-inline'` (inline styles needed for HTML)
- `frame-ancestors 'none'` (prevent clickjacking)
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: no-referrer`
- `X-Frame-Options: DENY`

### SSRF Protection (Webhooks)
- `webhook_manager.py` blocks private network IPs
- Validates target URL is not localhost, 10.x, 172.x, 192.168.x
- HMAC-SHA256 signing for webhook payloads

### CORS
- Configurable allowed origins
- Credentials enabled (cookies sent cross-origin)
- Methods restricted to GET, POST, PUT, DELETE

### Privilege System
- Per-user capabilities (can_use_agent, can_use_bash, etc.)
- Admin users get all privileges
- Non-admin users restricted by privilege flags
- Reserved usernames prevent impersonation

## Security Risks

1. **Shell access:** `bash` tool gives full shell access to the server when can_use_bash is True
2. **SQLite single-writer:** Concurrent writes can cause locking issues under load
3. **No rate limiting:** API endpoints have no built-in rate limiting
4. **Inline styles:** `'unsafe-inline'` for styles (low risk, visual only)
5. **Cookie auth:** No CSRF tokens (mitigated by CORS + same-origin policy)
6. **LOCALHOST_BYPASS:** Dangerous if enabled in production (any local process can access)

## Recommended Hardening

1. Enable rate limiting via reverse proxy (nginx/Caddy)
2. Use SECURE_COOKIES=true behind HTTPS
3. Keep LOCALHOST_BYPASS=false in production
4. Restrict can_use_bash to admin users only
5. Use ALLOWED_ORIGINS with specific public origin
6. Regular backup of data/ directory
7. Monitor auth.json for unauthorized changes

---

# 13. FEATURE-BY-FEATURE DEEP ANALYSIS

## Feature: Chat

**Purpose:** Primary interaction mode — conversational AI with persistent memory.

**Technical implementation:**
- **Backend:** `routes/chat_routes.py` (1227 lines), `src/chat_handler.py` (308 lines)
- **LLM:** `src/llm_core.py` — multi-provider streaming
- **Context:** `src/chat_processor.py` — memory, skills, RAG injection
- **Persistence:** `core/session_manager.py` — messages saved to DB
- **Streaming:** SSE with delta, thinking, metrics events

**Data flow:**
```
User input → preprocess (URLs, YouTube, images)
  → context build (memory, skills, RAG, history)
  → LLM call (stream with fallback)
  → SSE stream to browser
  → save response + extract memory
```

**UI layer:** `static/js/chat.js` (215KB), `chatRenderer.js` (103KB), `chatStream.js` (12KB)

## Feature: Agent Mode

**Purpose:** Tool-augmented conversation where the LLM can act on the world.

**Technical implementation:**
- **Loop:** `src/agent_loop.py` (2207 lines) — multi-round tool execution
- **Backend abstraction:** `src/agent_backend.py` — OpenCode + Hermes
- **Tool selection:** `src/tool_index.py` — RAG-based via ChromaDB
- **Tool schemas:** `src/tool_schemas.py` (1228 lines) — 60+ tools
- **Tool execution:** `src/agent_tools.py`, tool implementation files

**UI layer:** Same as chat, plus tool_start/tool_output rendering

## Feature: Deep Research

**Purpose:** Autonomous multi-round web research producing comprehensive reports.

**Technical implementation:**
- **Engine:** `src/deep_research.py` (830 lines)
- **Search:** `services/search/` — 6 provider fallback chain
- **Extraction:** `services/search/content.py` — web page parsing
- **Synthesis:** LLM-driven report generation
- **Storage:** `data/deep_research/` — saved reports

**UI layer:** `static/js/research/` — progress display, report viewer

## Feature: Email

**Purpose:** Full email client with IMAP/SMTP, multi-account, AI summarization.

**Technical implementation:**
- **Routes:** `routes/email_routes.py`, `routes/email_helpers.py`, `routes/email_pollers.py`
- **MCP server:** `mcp_servers/email_server.py` (1594 lines)
- **Accounts:** `EmailAccount` DB model (encrypted passwords)
- **Polling:** Background IMAP polling (configurable interval)
- **Summaries:** LLM-generated email summaries cached in SQLite

**Capabilities:** List, read, send, reply, archive, delete, bulk operations, multi-account

**UI layer:** `static/js/emailLibrary.js` (227KB), `emailInbox.js` (52KB)

## Feature: Calendar

**Purpose:** Event management with CalDAV sync.

**Technical implementation:**
- **Routes:** `routes/calendar_routes.py`
- **Sync:** `src/caldav_sync.py` — CalDAV protocol (PROPFIND + REPORT)
- **Libraries:** `caldav`, `python-dateutil`, `icalendar`
- **Providers:** Radicale, Nextcloud, Apple, Fastmail
- **ICS import/export:** `icalendar` library

**UI layer:** `static/js/calendar.js` (156KB), `static/js/calendar/`

## Feature: Notes

**Purpose:** Google Keep-style notes and checklists with reminders.

**Technical implementation:**
- **Routes:** `routes/note_routes.py`
- **Storage:** JSON file (`data/notes_*.json`)
- **Reminders:** Due dates trigger browser/email/ntfy notifications
- **Types:** Plain text, checklist (with checkboxes)

**UI layer:** `static/js/notes.js` (227KB)

## Feature: Tasks

**Purpose:** Scheduled task automation with cron expressions.

**Technical implementation:**
- **Scheduler:** `src/task_scheduler.py` (2202 lines)
- **Routes:** `routes/task_routes.py`
- **DB model:** `ScheduledTask` with cron, timezone, prompt, action
- **Actions:** Send prompt to LLM, run script, fire event
- **Shared cache:** Singleflight TTL cache for data fetch deduplication

**UI layer:** `static/js/tasks.js` (124KB)

## Feature: Documents

**Purpose:** Code/text editor with versioning and AI suggestions.

**Technical implementation:**
- **Routes:** `routes/document_routes.py`, `routes/document_helpers.py`
- **DB models:** `Document`, `DocumentVersion`
- **Operations:** Create, edit (find/replace), update (full rewrite), suggest (code review)
- **Versioning:** Each edit creates a version entry

**UI layer:** `static/js/document.js` (413KB), `documentLibrary.js` (177KB), `static/js/editor/` (34 files)

## Feature: Gallery

**Purpose:** Image management with AI generation and editing.

**Technical implementation:**
- **Routes:** `routes/gallery_routes.py`, `routes/gallery_helpers.py`
- **DB models:** `GalleryAlbum`, `GalleryImage`
- **AI generation:** `mcp_servers/image_gen_server.py` — DALL-E/GPT-image
- **AI editing:** Upscale, background removal (rembg), inpaint, harmonize
- **Storage:** `data/generated_images/`

**UI layer:** `static/js/gallery.js` (134KB), `galleryEditor.js` (157KB)

## Feature: Cookbook (Model Management)

**Purpose:** Download, serve, and manage local/remote AI models.

**Technical implementation:**
- **Routes:** `routes/cookbook_routes.py`, `routes/cookbook_helpers.py`
- **Hardware:** `services/hwfit/hardware.py` (600 lines) — GPU/CPU detection
- **Fit estimation:** `services/hwfit/fit.py` — VRAM requirements
- **Engines:** vLLM, SGLang, llama.cpp, Ollama, Diffusers
- **Remote:** SSH-based remote server management
- **tmux:** Model servers run in tmux sessions
- **Presets:** Saved serve configurations

**UI layer:** `static/js/cookbook.js` (101KB), `cookbookServe.js` (114KB), `cookbookRunning.js` (141KB), `cookbook-hwfit.js` (80KB), `cookbook-diagnosis.js` (31KB), `cookbookDownload.js` (21KB)

## Feature: Memory

**Purpose:** Persistent memory system for facts, preferences, and context.

**Technical implementation:**
- **Manager:** `src/memory.py` (370 lines), `services/memory/memory.py`
- **Vector store:** `services/memory/memory_vector.py` — ChromaDB semantic search
- **Extractor:** `services/memory/memory_extractor.py` — LLM extraction
- **Storage:** `data/memory.json` (JSON) + ChromaDB (vectors)
- **Categories:** fact, event, contact, preference, task

**UI layer:** `static/js/memory.js` (50KB)

## Feature: Skills

**Purpose:** Reusable AI procedures stored as structured markdown.

**Technical implementation:**
- **Manager:** `services/memory/skills.py` (642 lines)
- **Format:** `services/memory/skill_format.py` — YAML frontmatter + markdown
- **Extractor:** `services/memory/skill_extractor.py`
- **Storage:** `data/skills/<category>/<name>/SKILL.md`
- **Usage tracking:** `data/skills/_usage.json` sidecar

**UI layer:** `static/js/skills.js` (89KB)

## Feature: TTS (Text-to-Speech)

**Purpose:** Convert assistant responses to speech.

**Technical implementation:**
- **Service:** `services/tts/tts_service.py` (283 lines)
- **Routes:** `routes/tts_routes.py`
- **Providers:** disabled, browser (Web Speech API), local (Kokoro-82M), endpoint (OpenAI API)
- **Cache:** SHA-256 keyed file cache

**UI layer:** `static/js/tts-ai.js` (18KB)

## Feature: STT (Speech-to-Text)

**Purpose:** Voice input via microphone.

**Technical implementation:**
- **Service:** `services/stt/stt_service.py` (207 lines)
- **Routes:** `routes/stt_routes.py`
- **Providers:** disabled, browser, local (faster-whisper), endpoint

**UI layer:** `static/js/voiceRecorder.js` (8KB)

## Feature: Shell

**Purpose:** Execute shell commands on the server.

**Technical implementation:**
- **Service:** `services/shell/service.py` (162 lines)
- **Routes:** `routes/shell_routes.py`
- **Execution:** `asyncio.create_subprocess_shell`
- **Streaming:** Line-by-line output
- **Timeout:** Configurable, default 30s
- **Max output:** 200KB

## Feature: Web Search

**Purpose:** Search the web for current information.

**Technical implementation:**
- **Core:** `services/search/core.py` (436 lines)
- **Providers:** SearXNG, Brave, DuckDuckGo, Google PSE, Tavily, Serper
- **Fallback chain:** Configurable ordered provider list
- **Content extraction:** BeautifulSoup web page parsing
- **Caching:** File-based result cache
- **Analytics:** Error tracking, rate limit detection

## Feature: MCP (Model Context Protocol)

**Purpose:** External tool servers via standardized protocol.

**Technical implementation:**
- **Manager:** `src/mcp_manager.py` (429 lines)
- **Routes:** `routes/mcp_routes.py`
- **Transport:** stdio (subprocess) + SSE (HTTP)
- **Built-in servers:** email, memory, image_gen, rag
- **Per-server tool disabling** stored in DB

## Feature: Webhooks

**Purpose:** Outgoing HTTP notifications for app events.

**Technical implementation:**
- **Manager:** `src/webhook_manager.py` (227 lines)
- **Routes:** `routes/webhook_routes.py`
- **Security:** SSRF protection (blocks private IPs), HMAC-SHA256 signing
- **Events:** session.created, chat.completed, chat.message, webhook.test

## Feature: Companion (LAN Pairing)

**Purpose:** QR-code based device pairing for LAN access.

**Technical implementation:**
- **Routes:** `companion/routes.py` (236 lines)
- **Pairing:** `companion/pairing.py` — CSRF-safe token minting
- **QR codes:** `qrcode[pil]` library

## Feature: Integrations

**Purpose:** Connect to external services (RSS, git, bookmarks, smart home).

**Technical implementation:**
- **Module:** `src/integrations.py` (493 lines)
- **Presets:** Miniflux (RSS), Gitea (git), Linkding (bookmarks), Home Assistant
- **Credentials:** Encrypted storage
- **Access:** Via `api_call` tool in agent mode

## Feature: Hardware Detection (hwfit)

**Purpose:** Detect hardware capabilities for model serving recommendations.

**Technical implementation:**
- **Hardware:** `services/hwfit/hardware.py` (600 lines)
- **Fit:** `services/hwfit/fit.py` (527 lines)
- **GPU detection:** NVIDIA (nvidia-smi), AMD (rocm-smi), Apple (system_profiler)
- **Remote SSH:** Probe remote servers for hardware
- **GPU grouping:** Homogeneous pools for tensor parallel serving
- **Cache:** 30-minute TTL

---

# 14. CURRENT CUSTOM MODIFICATIONS ANALYSIS

## Identified Customizations

### Self-Hosted Search Stack
- **SearXNG** configured as primary search provider with custom settings template
- Custom engine pinning: `SEARXNG_GENERAL_ENGINES=bing,mojeek,presearch` (default engines rate-limited)
- DuckDuckGo as default fallback (no API key required)

### Multi-Provider LLM Configuration
- OpenRouter + Grok + Ollama + xAI configured simultaneously
- Custom fallback chains for different use cases
- Tailscale-aware endpoint resolution for distributed model hosting

### Cookbook Model Management
- Full model serving infrastructure (vLLM, SGLang, llama.cpp)
- Remote GPU server management via SSH
- Custom hardware detection with remote probing
- tmux-based model server lifecycle management

### Docker Infrastructure
- Custom entrypoint with PUID/PGID privilege dropping
- SearXNG secret injection at first boot
- GPU overlay support (NVIDIA + AMD)
- host.docker.internal for host Ollama access

### Authentication Customization
- Multi-user system with granular privileges
- TOTP 2FA support
- API tokens for programmatic access
- Internal-tool token for agent loopback

### Theme System
- 103KB theme.js with CSS variable management
- Custom font system in `/static/fonts/`
- Dynamic theme creation and switching

### Agent System Extensions
- Hermes backend abstraction for external agent services
- 60+ tools with RAG-based selection
- MCP server integration for external tools
- Custom tool security model

## Architecture Changes from Upstream

The codebase shows signs of significant evolution from a simpler chat application:
- Original single-file chat app → modular FastAPI with 47 route files
- Simple LLM call → multi-provider abstraction with failover
- No agent capability → full agentic system with 60+ tools
- No persistence → SQLAlchemy with 20+ tables
- No search → 6-provider search with fallback chains
- No scheduling → full cron system with timezone support

---

# 15. COMPLETE RUNTIME EXECUTION FLOW

## Boot Sequence (Docker)

```
docker compose up
  → Docker builds image from Dockerfile
  → entrypoint.sh runs:
    1. Read PUID=1000, PGID=1000
    2. Create odysseus user/group
    3. chown /app/data, /app/logs
    4. Detect CUDA_HOME
    5. gosu odysseus → exec uvicorn app:app --host 0.0.0.0 --port 7000
  → uvicorn loads app.py:
    1. register_static_mime_types()
    2. Windows symlink workaround
    3. load_dotenv()
    4. Create FastAPI app
    5. Add middleware (CORS, Security, Timeout, Auth)
    6. Mount static files
    7. initialize_managers() → create all component instances
    8. Register 47 route modules
    9. Register startup/shutdown event handlers
    10. uvicorn starts listening on port 7000
  → Startup event fires:
    a. Agent manager start (register OpenCode + Hermes backends)
    b. Purge incognito sessions
    c. Schedule upload cleanup timer
    d. Start background monitor
    e. Connect MCP servers (stdio subprocesses)
    f. Warm tool index (embed tool descriptions in ChromaDB)
    g. Warm LLM endpoints (HEAD requests to check health)
    h. Create default scheduled tasks (if none exist)
    i. Backfill skill owners (add owner to ownerless skills)
    j. Start task scheduler (background thread)
    k. Sweep null-owner sessions
    l. Schedule nightly skill audit
  → Application ready
```

## Service Initialization Order

```
1. searxng container starts (healthcheck: 5s interval, 20 retries)
2. chromadb container starts
3. odysseus container starts (depends_on: searxng healthy + chromadb started)
4. ntfy container starts (independent)
```

## Frontend Loading

```
Browser requests /
  → FastAPI serves static/index.html
  → Browser loads:
    1. style.css (1084KB)
    2. lib/ (third-party: marked.js, highlight.js, etc.)
    3. app.js (172KB) — core router
    4. js/init.js — startup sequence
    5. Feature modules loaded on demand
  → init.js:
    1. Check auth status (GET /api/auth/status)
    2. If not authenticated → redirect to /login
    3. Load settings (GET /api/settings)
    4. Load sessions (GET /api/sessions)
    5. Initialize UI panels
    6. Set up event listeners
    7. Apply theme
    8. Show main chat panel
```

## Provider Registration

```
ModelDiscovery at startup:
  1. Scan LLM_HOST + LLM_HOSTS for endpoints
  2. Port scan 8000-8020 + 11434 on each host
  3. Try Tailscale hostname resolution
  4. Query each endpoint for model list
  5. Add built-in providers (OpenAI, xAI if keys set)
  6. Store discovered endpoints in DB (ModelEndpoint table)
  7. Cache model lists per endpoint
```

## Agent Initialization

```
AgentManager.start():
  1. Create OpenCodeBackend instance
  2. Create HermesBackend instance (if HERMES_URL configured)
  3. Register both backends
  4. Read AGENT_BACKEND env var or settings.json
  5. Set active backend
  6. Call initialize() on all registered backends
  7. Health check all backends
```

## Task Execution Lifecycle

```
TaskScheduler.start():
  1. Load all ScheduledTask from DB
  2. For each task: compute_next_run()
  3. Sort by next_run time
  4. Start background asyncio loop:
     a. Sleep until earliest next_run
     b. Fire task:
        - Resolve endpoint + model
        - Build prompt with context
        - Send to LLM (agent mode with ASSISTANT_ALWAYS_AVAILABLE tools)
        - Store result
        - Send notification (browser/email/ntfy)
        - Compute next run
        - Update DB
     c. Repeat
```

## Shutdown Lifecycle

```
SIGTERM/SIGINT received
  → uvicorn graceful shutdown
  → FastAPI shutdown event fires:
    1. agent_manager.shutdown() — stop all backends
    2. Cancel upload cleanup timer
    3. task_scheduler.stop() — stop background loop
    4. webhook_manager.close() — close HTTP client
    5. mcp_manager.disconnect() — terminate MCP subprocesses
  → uvicorn exits
  → Docker container stops
```

---

# 16. SYSTEM DEPENDENCY GRAPH

## Critical Dependency Chains

### Chat → LLM Chain
```
chat_routes → chat_handler → chat_processor → llm_core → HTTP endpoint
  Dependencies: network, provider availability, API keys, model health
  Failure: 503 error, fallback to next model in chain
```

### Agent → Tool Chain
```
chat_routes → agent_backend → agent_loop → tool_index → tool execution
  Dependencies: ChromaDB (tool selection), tool implementations, MCP servers
  Failure: tool error surfaced to LLM, LLM decides retry or report
```

### Research → Search Chain
```
research_routes → deep_research → search service → search providers
  Dependencies: SearXNG, Brave/DDG/Google, web page accessibility, LLM
  Failure: fallback to next search provider, reduced results
```

### Email → IMAP Chain
```
email_routes → email_server → IMAP server
  Dependencies: network, IMAP credentials, mail server availability
  Failure: connection error, retry on next poll
```

## Coupling Analysis

### Tight Coupling
- `app.py` depends on all route modules (import-time)
- `agent_loop.py` depends on `llm_core.py`, `tool_index.py`, `tool_schemas.py`
- `chat_routes.py` depends on `chat_handler.py`, `session_manager.py`, `database.py`

### Loose Coupling
- Services are independent modules (imported on demand)
- MCP servers run as separate processes (stdio communication)
- Frontend JS modules are independent ES modules
- Search providers are interchangeable via provider chain

## Failure Points

1. **ChromaDB down:** Tool selection falls back to keyword matching, memory vector search unavailable
2. **SearXNG down:** Search falls back to DuckDuckGo or configured chain
3. **LLM endpoint down:** Dead-host cooldown, fallback chain tries next model
4. **SQLite locked:** Concurrent write conflict, retry needed
5. **MCP server crash:** Tools from that server unavailable, others unaffected
6. **Network partition:** External APIs unreachable, local features still work

## Bottlenecks

1. **SQLite single-writer:** All DB writes serialized, bottleneck under high concurrency
2. **Shared httpx client:** Connection pool (100 max) shared across all LLM calls
3. **Synchronous tool execution:** Tools execute sequentially within an agent round
4. **Research concurrency:** Web page extraction limited to `research_extraction_concurrency` (default 3)
5. **Memory file I/O:** JSON file reads/writes for memory (no database index)

---

# 17. FUTURE DEVELOPMENT GUIDE

## Safest Extension Points

### Adding a New LLM Provider
1. Add provider detection in `src/llm_core.py:_detect_provider()`
2. Add format conversion in `stream_llm()` (messages, auth headers, URL)
3. Add to `src/endpoint_resolver.py:build_chat_url()` for URL building
4. No other changes needed — the abstraction layer handles everything

### Adding a New Agent Backend
1. Subclass `AgentBackend` in `src/agent_backend.py`
2. Implement `stream()`, `initialize()`, `shutdown()`, `is_healthy()`
3. Yield SSE events matching the contract (delta, tool_start, tool_output, etc.)
4. Register in `AgentManager.setup_default_backends()`
5. Add to settings `agent_backend` options

### Adding a New Tool
1. Add tool implementation in tool implementation files
2. Add OpenAI function schema to `FUNCTION_TOOL_SCHEMAS` in `src/tool_schemas.py`
3. Add description to `BUILTIN_TOOL_DESCRIPTIONS` in `src/tool_index.py`
4. Add to `ALWAYS_AVAILABLE` if it should never be filtered by RAG
5. Add `TOOL_TAGS` entry in `src/agent_tools.py` for parsing
6. The tool becomes available to the agent automatically via RAG selection

### Adding a New Search Provider
1. Add provider function in `services/search/providers.py`
2. Add to `PROVIDER_INFO` registry
3. Add case in `services/search/core.py:_call_provider()`
4. Add settings key for API key in `DEFAULT_SETTINGS`
5. Add to settings UI in `static/js/settings.js`

### Adding a New MCP Server
1. Create `mcp_servers/new_server.py` following the pattern:
   ```python
   server = Server("name")
   @server.list_tools() → list[Tool]
   @server.call_tool() → list[TextContent]
   async def run(): async with stdio_server() as (r, w): await server.run(r, w, ...)
   ```
2. Add to database `McpServer` table (via admin UI or API)
3. Configure transport (stdio command or SSE URL)
4. Restart app or reconnect via `/api/mcp/reconnect`

### Adding a New UI Panel
1. Add HTML structure to `static/index.html`
2. Add JS module in `static/js/`
3. Add route in `static/app.js` router
4. Add SPA fallback in `app.py` (`@app.get("/new-panel")`)
5. Add API routes in `routes/new_panel_routes.py`
6. Register routes in `app.py`

### Adding a New Scheduled Task Type
1. Add action type in `src/task_scheduler.py`
2. Add task creation UI in `static/js/tasks.js`
3. Add DB columns to `ScheduledTask` if needed (migration)
4. Add to `HOUSEKEEPING_DEFAULTS` if built-in

## Recommended Architecture Practices

1. **Keep services independent** — import on demand, not at module top
2. **Use the abstraction layers** — never call provider APIs directly
3. **Atomic writes for config** — always use `atomic_write_json()`
4. **Owner-scoped data** — always filter by `owner` column
5. **SSE for streaming** — never WebSocket (keeps things simple)
6. **Fallback chains** — always configure fallbacks for critical services
7. **Encrypted credentials** — use `EncryptedText` for any secrets in DB
8. **Test with auth enabled** — most bugs surface with auth middleware active

## How to Avoid Breaking Architecture

1. **Don't add circular imports** — `src/` should not import from `routes/`
2. **Don't bypass middleware** — use the internal-tool token for loopback, not auth skip
3. **Don't hardcode endpoints** — always use `endpoint_resolver`
4. **Don't skip tool security** — always check `blocked_tools_for_owner`
5. **Don't store secrets in settings.json** — use `EncryptedText` columns or `secret_storage`
6. **Don't assume single user** — always scope by owner

---

# 18. PERFORMANCE + SCALING ANALYSIS

## Performance Characteristics

### Startup Time
- **Fast:** <3 seconds for core initialization
- **ChromaDB warmup:** Adds 2-5 seconds for tool index embedding
- **LLM endpoint warmup:** Adds 1-3 seconds for health checks
- **Total:** ~5-10 seconds to fully operational

### Memory Usage
- **Base Python process:** ~150-250MB
- **fastembed ONNX model:** ~50MB
- **httpx connection pool:** ~10-20MB (100 connections)
- **ChromaDB client:** ~10-20MB
- **SQLite cache:** ~10-50MB depending on DB size
- **Total:** ~250-400MB typical

### Request Latency
- **Static files:** <5ms (served by Starlette)
- **API CRUD:** 10-50ms (SQLite query)
- **LLM first token:** 200ms-5s depending on provider/model
- **Agent round:** 2-30s depending on tool count and model
- **Research job:** 2-30 minutes depending on topic depth
- **Search:** 1-5s depending on provider

### Concurrency
- **Async I/O:** FastAPI handles 100+ concurrent requests
- **SQLite bottleneck:** Writes serialized (WAL mode helps)
- **Connection pool:** 100 max concurrent LLM API connections
- **Agent sessions:** Each agent run holds a streaming connection

## Optimization Opportunities

1. **PostgreSQL migration:** Replace SQLite for concurrent write support
2. **Redis caching:** Replace file-based caches with Redis for multi-process
3. **Connection reuse:** Already implemented (shared httpx client)
4. **Streaming optimization:** Already using SSE (efficient, HTTP-compatible)
5. **Tool execution parallelism:** Currently sequential, could parallelize independent tools
6. **Search result deduplication:** Cross-provider dedup for fallback chains

## Scaling Limitations

1. **Single-process:** uvicorn runs one worker (FastAPI async handles concurrency)
2. **SQLite:** Not suitable for >10 concurrent writers
3. **In-memory caches:** Not shared across processes (settings, tokens, dead hosts)
4. **No horizontal scaling:** Designed as single-instance self-hosted app
5. **File-based storage:** JSON files don't scale beyond single-instance
6. **MCP subprocesses:** One set per process, can't share across instances

---

# 19. KNOWN RISKS + TECHNICAL DEBT

## Dangerous Patterns

1. **Global mutable state:** Dead-host maps, token caches, settings caches are module-level globals
2. **Thread safety gaps:** Some globals protected by locks, some not (e.g., `_model_activity`)
3. **Import-time side effects:** `load_dotenv()` at module top, `register_static_mime_types()` at top
4. **Large file I/O:** `document.js` is 413KB, `style.css` is 1084KB — slow on mobile

## Architectural Weaknesses

1. **Monolithic app.py:** 1065 lines with all route registrations and lifecycle events
2. **Duplicate code:** MemoryManager exists in both `src/memory.py` and `services/memory/memory.py`
3. **Mixed patterns:** Some routes use class-based handlers, others use functions
4. **No service layer:** Routes often access DB directly (no repository pattern)
5. **Frontend size:** 189KB index.html + 1084KB CSS + 172KB app.js = 1.4MB before modules

## Security Risks

1. **Shell tool:** Full system access when bash privilege enabled
2. **No rate limiting:** DoS possible via rapid API calls
3. **LOCALHOST_BYPASS:** Dangerous if accidentally enabled in production
4. **Inline styles CSP:** `'unsafe-inline'` for styles (low risk)
5. **Fernet key:** If `data/.app_key` is stolen, all encrypted data is compromised
6. **No audit logging:** No record of who did what (auth events, data changes)

## Maintainability Concerns

1. **Large files:** `agent_loop.py` (2207), `task_scheduler.py` (2202), `database.py` (1858), `llm_core.py` (1296), `tool_schemas.py` (1228) — difficult to navigate
2. **JS modules:** `document.js` (413KB), `slashCommands.js` (255KB), `emailLibrary.js` (227KB), `notes.js` (227KB) — extremely large single files
3. **No type hints:** Many functions lack type annotations
4. **Comment-heavy:** Good documentation but some comments explain workarounds for bugs
5. **No API versioning:** All routes are `/api/*` with no version prefix

## Fragile Systems

1. **MCP subprocess management:** stdio-based, can hang or zombie
2. **tmux model servers:** Rely on tmux session management (fragile across reboots)
3. **IMAP polling:** Background threads connecting to mail servers (timeout-prone)
4. **JSON file storage:** Memory, settings, sessions — corruption risk on crash
5. **ChromaDB dependency:** Tool selection degrades if ChromaDB unavailable

## Technical Debt

1. **Duplicate memory modules:** `src/memory.py` and `services/memory/memory.py` contain similar code
2. **Legacy session format:** `sessions.json` alongside DB sessions (migration incomplete)
3. **No migration system:** DB schema changes require manual `update_database.py` script
4. **No test coverage documentation:** 88 test files but unclear coverage
5. **CSS monolith:** 1MB+ single CSS file with no modular organization

---

# 20. COMPLETE FINAL SYSTEM SUMMARY

## Complete Mental Model

Odysseus is a **self-hosted AI operating system** that runs as a single Docker Compose deployment (4 containers: odysseus, chromadb, searxng, ntfy). The core is a FastAPI monolith serving both a REST API and a vanilla JS SPA frontend.

The system provides a **multi-provider LLM abstraction** that communicates with any OpenAI-compatible, Anthropic, or Ollama endpoint, with automatic failover chains and dead-host cooldown. On top of this sits an **agentic layer** with 60+ tools selected via RAG (ChromaDB embeddings), executed in multi-round loops where the LLM decides when to use tools and when to stop.

**Persistence** is primarily SQLite with JSON files for configuration, Fernet encryption for secrets, and ChromaDB for vector operations. The **frontend** is a massive single-page app (189KB HTML, 1MB CSS, 172KB core JS, 73 modules) with no build step.

**Key subsystems** include: deep research (iterative web search + synthesis), email (IMAP/SMTP with AI summarization), calendar (CalDAV sync), notes/tasks (Google Keep-style), documents (code editor with versioning), gallery (AI image gen/edit), cookbook (model serving infrastructure), memory (persistent facts + vector search), skills (reusable procedures), and shell (command execution).

**Infrastructure** is Docker-native with GPU passthrough support, PUID/PGID privilege dropping, Tailscale-aware networking, and health-checked service dependencies.

## How All Systems Connect

```
Browser (SPA) ──HTTP/SSE──► FastAPI (app.py)
                              │
              ┌───────────────┼───────────────────┐
              ▼               ▼                   ▼
         Routes (48)    Middleware Chain     Static Files
              │         (CORS, CSP,           (HTML, JS, CSS)
              │          Timeout, Auth)
              ▼
         src/ (Business Logic)
         ├── llm_core.py ────────► External LLM APIs
         ├── agent_loop.py ──────► Tool Execution
         │   ├── tool_index.py ──► ChromaDB
         │   ├── tool_schemas.py
         │   └── tool_implementations
         ├── chat_handler.py ────► Context Building
         ├── deep_research.py ───► Search + LLM
         ├── task_scheduler.py ──► Cron + Events
         ├── settings.py ────────► JSON Config
         └── endpoint_resolver.py► Tailscale + DB
              │
              ▼
         core/ (Infrastructure)
         ├── database.py ────────► SQLite (20+ tables)
         ├── auth.py ────────────► bcrypt + TOTP
         ├── session_manager.py ─► Lazy Hydration
         ├── middleware.py ──────► CSP + Token
         └── atomic_io.py ───────► Safe File I/O
              │
              ▼
         services/ (Capabilities)
         ├── search/ ────────────► SearXNG, Brave, DDG, Google, Tavily, Serper
         ├── memory/ ────────────► JSON + ChromaDB + LLM Extraction
         ├── shell/ ─────────────► subprocess
         ├── tts/ ───────────────► Kokoro + API
         ├── stt/ ───────────────► Whisper + API
         ├── hwfit/ ─────────────► nvidia-smi + SSH
         └── youtube/ ───────────► Transcript API
              │
              ▼
         mcp_servers/ (External Tools)
         ├── email_server.py ────► IMAP/SMTP
         ├── memory_server.py ───► Memory Manager
         ├── image_gen_server.py ► DALL-E API
         └── rag_server.py ──────► Personal Docs
              │
              ▼
         Docker Services
         ├── chromadb:8000 ──────► Vector Store
         ├── searxng:8080 ───────► Web Search
         └── ntfy:8091 ──────────► Notifications
```

---

# AI CONTEXT HANDOFF SECTION

## System Intelligence Summary

**Platform:** Odysseus — self-hosted AI assistant platform (v0.9.1)
**Stack:** Python/FastAPI + vanilla JS SPA + SQLite + ChromaDB + Docker
**Deployment:** Docker Compose (4 services: odysseus, chromadb, searxng, ntfy)
**Entry point:** `app.py` → `uvicorn app:app --host 0.0.0.0 --port 7000`

## Critical Architecture Patterns

1. **Provider-agnostic LLM layer:** `src/llm_core.py` abstracts all providers (OpenAI, Anthropic, Ollama, OpenRouter, Groq, xAI) behind `stream_llm()` and `stream_llm_with_fallback()`.
2. **Agent backend abstraction:** `src/agent_backend.py` defines ABC. OpenCode (built-in) and Hermes (external) implement it. Manager is thread-safe singleton.
3. **RAG tool selection:** `src/tool_index.py` embeds 60+ tool descriptions in ChromaDB, retrieves top-K relevant per message. ALWAYS_AVAILABLE tools never filtered.
4. **SSE streaming everywhere:** Chat, agent, shell, research all use Server-Sent Events. No WebSocket.
5. **Multi-path auth:** Cookie sessions, Bearer tokens (ody_ prefix), internal-tool token, LOCALHOST_BYPASS.
6. **Encrypted at rest:** Fernet encryption via `EncryptedText` TypeDecorator for DB secrets.
7. **Atomic config writes:** `atomic_write_json()` — write-to-temp + fsync + os.replace.
8. **Lazy session hydration:** Metadata at boot, messages on first access.
9. **Dead-host cooldown:** 20s after 2 consecutive failures. Thread-safe.
10. **Singleflight cache:** Shared TTL cache in task scheduler deduplicates concurrent fetches.

## Important Warnings

- **Never name a user "internal-tool"** — reserved for agent loopback auth bypass
- **Always use endpoint_resolver** — never hardcode LLM URLs
- **Always scope by owner** — multi-user data isolation depends on it
- **Don't bypass middleware** — use internal-tool token for loopback calls
- **SQLite is single-writer** — concurrent writes can lock
- **JSON files can corrupt** — always use atomic_write_json
- **Shell tool = full system access** — restrict via privileges
- **ChromaDB required for tool selection** — degrades to keyword matching if down
- **MCP servers are subprocesses** — can hang/zombie, need monitoring

## Extension Rules

- **New provider:** Add detection in `_detect_provider()`, format conversion in `stream_llm()`
- **New tool:** Add schema to `FUNCTION_TOOL_SCHEMAS`, description to `BUILTIN_TOOL_DESCRIPTIONS`, implementation
- **New backend:** Subclass `AgentBackend`, implement 4 methods, register in manager
- **New search provider:** Add to `PROVIDER_INFO`, implement provider function, add to `_call_provider()`
- **New MCP server:** Create `mcp_servers/new_server.py`, register in DB, configure transport
- **New route:** Create `routes/new_routes.py` with `setup_*_routes() -> APIRouter`, register in `app.py`
- **New panel:** Add HTML to `index.html`, JS module to `static/js/`, SPA route in `app.py`

## Runtime Behavior

- **Startup:** 5-10s (includes ChromaDB warmup + endpoint health checks)
- **Memory:** 250-400MB typical
- **Chat latency:** 200ms-5s to first token
- **Agent round:** 2-30s depending on tools
- **Research:** 2-30 minutes
- **Streaming:** SSE with delta/thinking/tool_start/tool_output/metrics/[DONE] events

## Key Integration Points

- **LLM APIs:** OpenAI-compatible (default), Anthropic native, Ollama native
- **Search:** SearXNG (primary), Brave, DuckDuckGo, Google PSE, Tavily, Serper
- **Vector:** ChromaDB (Docker container on port 8100)
- **Embeddings:** HTTP API (Ollama) or local fastembed (ONNX)
- **Notifications:** ntfy (Docker container on port 8091), browser, email
- **Calendar:** CalDAV (Radicale, Nextcloud, Apple, Fastmail)
- **Email:** IMAP/SMTP with multi-account support
- **Model serving:** vLLM, SGLang, llama.cpp, Ollama via tmux sessions
- **External tools:** MCP protocol (stdio + SSE transport)
- **Network:** Tailscale-aware hostname resolution

## File Quick Reference

| File | Purpose |
|------|---------|
| `app.py` | Main orchestrator — middleware, routes, lifecycle |
| `core/database.py` | All DB models (20+ tables) |
| `core/auth.py` | Multi-user auth + TOTP 2FA |
| `src/llm_core.py` | LLM communication (all providers) |
| `src/agent_loop.py` | Agent execution loop (tool parsing + execution) |
| `src/tool_index.py` | RAG-based tool selection (ChromaDB) |
| `src/tool_schemas.py` | OpenAI function schemas (60+ tools) |
| `src/task_scheduler.py` | Cron task execution |
| `src/deep_research.py` | Autonomous research engine |
| `src/endpoint_resolver.py` | Unified endpoint resolution |
| `src/settings.py` | Centralized settings (TTL cached) |
| `services/search/core.py` | Search orchestrator (6 providers) |
| `services/memory/skills.py` | Skills manager (SKILL.md files) |
| `docker-compose.yml` | 4-service infrastructure |
| `.env.example` | All environment variables |

---

*End of ODYSSEUS_COMPLETE_SYSTEM_ARCHITECTURE.md — Living Document*
*Generated from complete codebase analysis*
