# Hunter — AI Agent Context

Use this document to onboard any AI assistant (Claude, GPT, Copilot, etc.) onto this codebase. Copy-paste it into a new session or attach it as context.

---

## What This App Does

Hunter is a **self-hosted, single-user job search automation platform**. It runs entirely on your machine via Docker Compose. The goal is to automate the tedious parts of job hunting:

1. **Discover** — Automatically scrape job listings from multiple job boards on a schedule
2. **Score** — Rate each job 0-100 against your profile (keywords, title, location preference)
3. **Search** — Full-text search across all discovered jobs
4. **Apply** — Semi-automated form filling with Playwright (always pauses for human review before submitting)
5. **Track** — Dashboard with stats, charts, and real-time updates via WebSocket

There is **no authentication** — it's designed for a single user running it locally. The user profile is auto-created on first access.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui |
| Backend | Python 3.12 + FastAPI (fully async) + SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16 (tsvector full-text search, GIN index, UUID PKs) |
| Migrations | Alembic (async-compatible, strips `+asyncpg` for sync operations) |
| Task Queue | Celery + Redis (broker & result backend) |
| Scraping | Playwright (Python, headless Chromium) |
| Real-time | WebSocket + Redis pub/sub (bridge between Celery workers and frontend) |
| AI | Anthropic Claude API (for free-text application question answering) |
| Email | Resend API (primary) + SMTP (fallback) |
| Infrastructure | Docker Compose (6 services) |

---

## Project Structure

```
hunter/
├── backend/                    # FastAPI + Celery (Python 3.12)
│   ├── app/
│   │   ├── main.py            # FastAPI entry point, CORS, routers, WS listener
│   │   ├── config.py          # pydantic-settings from .env
│   │   ├── database.py        # Async SQLAlchemy engine + session
│   │   ├── models/            # ORM: JobBoard, Job, UserProfile, Application, etc.
│   │   ├── schemas/           # Pydantic request/response models
│   │   ├── api/               # Route handlers (boards, jobs, profile, autoapply, websocket)
│   │   ├── services/          # Business logic (scanner, matcher, autofill, notifier, ai_assistant)
│   │   └── tasks/             # Celery tasks (scan_tasks, apply_tasks, celery_app config)
│   ├── alembic/               # DB migrations
│   ├── tests/                 # 122 tests (pytest, no external services needed)
│   └── requirements.txt
├── frontend/                   # React SPA (TypeScript)
│   └── src/
│       ├── pages/             # Dashboard, Boards, Jobs, AutoApply, Profile, Settings
│       ├── lib/api.ts         # Type-safe REST client (boardsApi, jobsApi, profileApi, applicationsApi)
│       ├── hooks/             # useWebSocket, useJobs
│       ├── types/index.ts     # TypeScript interfaces (manually synced with backend schemas)
│       └── components/ui/     # shadcn/ui primitives
├── scrapers/                   # Playwright scrapers (shared across backend services)
│   ├── base_scraper.py        # Abstract base: scrape() lifecycle, extract_jobs(), go_to_next_page()
│   ├── generic_scraper.py     # CSS selector-driven, configurable per board
│   ├── greenhouse_scraper.py  # Greenhouse ATS (boards.greenhouse.io)
│   ├── lever_scraper.py       # Lever ATS (jobs.lever.co)
│   ├── workday_scraper.py     # Workday ATS (*.myworkdayjobs.com)
│   └── utils.py               # robots.txt, random delays, user agent rotation, URL normalization
├── docker-compose.yml          # 6 services: postgres, redis, backend, celery-worker, celery-beat, frontend
├── .env.example                # Template for required environment variables
├── CLAUDE.md                   # Dev commands and conventions for Claude Code
└── DECISIONS.md                # Architecture decisions log
```

---

## Key Data Flows

### Job Scanning Pipeline
```
Celery beat (every 60s) → check_scan_schedules()
  → scan_board_task(board_id) per due board
    → Scraper.scrape(url) → list of job dicts
    → scanner.store_scraped_jobs() → dedup via SHA256 hash, parse salary, insert
    → matcher.score_jobs() → rate 0-100 (40% keyword, 35% title, 25% location)
    → broadcast "new_job" via Redis pub/sub → WebSocket → frontend
    → notifier.notify_new_jobs() → email
```

### Auto-Apply Flow (Human-in-the-Loop)
```
User clicks "Auto-Apply" → Celery task launches Playwright
  → Navigate to job URL → Detect form fields via heuristics
  → Auto-fill from profile with confidence scoring
  → If low confidence or CAPTCHA detected:
    → PAUSE → take screenshot → save form state → notify user
    → User reviews in UI, optionally requests AI-generated answers
    → User clicks "Submit" → bot resumes and submits
  → Full audit log recorded
```

**Critical rule:** Auto-apply NEVER submits without explicit user confirmation.

### Real-time Updates (WebSocket Bridge)
```
Celery worker → broadcast_sync() → Redis pub/sub channel "hunter:ws_broadcast"
FastAPI background task → ws_listener() → subscribes to Redis → forwards to WebSocket clients
Event types: new_job, application_update, scan_error
```

This bridge exists because Celery workers run in separate processes and can't directly access FastAPI's WebSocket connections.

---

## Code Conventions

- **Backend:** async/await throughout, type hints on all functions, structlog JSON logging
- **Frontend:** strict TypeScript, functional components, default exports for pages, named exports for API clients
- **Models:** UUID primary keys, `Mapped[T]` annotations, `created_at`/`updated_at` on all tables
- **Imports:** Scraper tests use `sys.path.insert` with relative `os.path` (not hardcoded paths)
- **Settings:** Backend config via `.env` + pydantic-settings; frontend settings in localStorage
- **Path alias:** `@/*` maps to `./src/*` in frontend

---

## API Surface

### REST Endpoints
- `GET/POST/PUT/DELETE /api/boards` — Board CRUD + `POST /{id}/scan` for manual scan trigger
- `GET /api/jobs` — List with filters (search, board_id, min_score, location, posted_days, sort_by) + pagination
- `GET /api/jobs/recent?days=7` — Recent jobs by posted date
- `PATCH /api/jobs/{id}/hide` | `/read` — Job UI state
- `GET/PUT /api/profile` — Single user profile + resume upload + education/experience CRUD
- `GET/POST /api/applications` — Auto-apply lifecycle + `/{id}/review`, `/{id}/ai-assist`, `/{id}/cancel`
- `GET /api/applications/dashboard` — Aggregated stats for dashboard

### WebSocket
- `ws://localhost:8000/ws` — Real-time events (new_job, application_update, scan_error)

---

## Development Commands

```bash
# Backend
cd backend
uvicorn app.main:app --reload --port 8000          # API server
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4
celery -A app.tasks.celery_app beat --loglevel=info
pytest tests/ -v                                    # 122 tests, no external deps needed
alembic upgrade head                                # Apply migrations

# Frontend
cd frontend
npm install && npm run dev                          # Vite dev server (port 5173)

# Docker (everything)
cp .env.example .env  # Edit with your values
docker compose up -d
```

---

## Testing Overview

122 tests across 8 files. No running PostgreSQL or Redis required.

- **Unit tests** mock Playwright elements to test scraper extraction logic
- **Integration tests** use in-memory SQLite with `@compiles` hooks mapping PG types (JSONB→TEXT, TSVECTOR→TEXT, UUID→VARCHAR)
- **Coverage:** scanner utilities, matcher scoring algorithm, autofill field detection, all 4 scraper types, recent jobs API endpoint

---

## Known Issues

- `test_matcher.py::TestComputeLocationScore::test_no_match` — pre-existing bug in location scoring logic
- `tsc --noEmit` shows `import.meta.env` errors — needs `vite/client` types reference
- Frontend TypeScript types are manually synced with backend Pydantic schemas (no codegen)

---

## When Working on This Codebase

1. Read the relevant model/schema files before changing API behavior
2. All Alembic models must be imported in `alembic/env.py` for autogenerate to work
3. Alembic uses a sync DB URL (strips `+asyncpg` from DATABASE_URL)
4. The scrapers package lives at the repo root (not inside backend/) and is mounted into Docker containers at `/opt/scrapers`
5. After any Dockerfile change, rebuild with `docker compose build --no-cache`
6. The single-user design means no auth middleware — don't add it
