# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Backend
```bash
cd backend
uvicorn app.main:app --reload --port 8000          # FastAPI dev server
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4  # Celery worker
celery -A app.tasks.celery_app beat --loglevel=info  # Celery beat scheduler
pytest tests/ -v                                    # Run all tests
pytest tests/test_scanner.py -v                     # Run single test file
pytest tests/test_scanner.py::TestClassName::test_method -v  # Run single test
alembic upgrade head                                # Apply migrations
alembic revision --autogenerate -m "description"    # Create migration
```

### Frontend
```bash
cd frontend
npm run dev       # Vite dev server (port 5173, proxies /api and /ws to backend:8000)
npm run build     # Production build
```

## Docker
- When debugging Docker issues, always check `docker compose logs <service>` before suggesting code changes.
- Never assume Docker socket permissions — ask the user about their Docker setup first.
- After any Dockerfile change, remind the user to rebuild with `docker compose build --no-cache`.

Requires PostgreSQL 16 (port 5432) and Redis 7 (port 6379) when running locally. Config loaded from `.env` (see `.env.example`).

## Architecture

**Single-user full-stack job search automation app.** No auth — the user profile is auto-created on first GET.

### Stack
- **Frontend:** React 18 + TypeScript + Vite + Tailwind + shadcn/ui
- **Backend:** Python 3.12 + FastAPI (async) + SQLAlchemy 2.0 (async) + Alembic
- **Queue:** Celery + Redis (broker & result backend)
- **Scraping:** Playwright (Python, headless Chromium)
- **DB:** PostgreSQL with tsvector full-text search (GIN index, auto-update trigger)
- **AI:** Anthropic Claude API (model configurable via `ANTHROPIC_MODEL` env var)

### Data Flow: Job Scanning
1. Celery beat runs `check_scan_schedules()` every 60s
2. Dispatches `scan_board_task(board_id)` for each board due for scanning
3. Scraper (selected by `scraper_config.scraper_type`) returns job dicts
4. `scanner.store_scraped_jobs()` deduplicates via content hash and inserts
5. `matcher.score_jobs()` scores 0–100 against user profile (40% keyword, 35% title similarity, 25% location)
6. Broadcasts `new_job` events via Redis pub/sub → WebSocket → frontend

### Real-time: WebSocket + Redis Pub/Sub
Celery workers can't send WebSocket messages directly. Instead:
- Workers call `broadcast_sync()` which publishes to Redis channel `hunter:ws_broadcast`
- FastAPI background task `ws_listener()` subscribes and forwards to connected WebSocket clients
- Event types: `new_job`, `scan_error`

### Application Tracking
Applications are tracked through these statuses: `applied`, `interviewing`, `offered`, `rejected`, `withdrawn`, `archived`. Users log applications manually (or via future Chrome extension) and update status as they progress. Full activity log tracks every change.

### Backend Structure
- `app/models/` — SQLAlchemy ORM (UUID PKs, `Mapped[T]` annotations, `created_at`/`updated_at` on all tables)
- `app/schemas/` — Pydantic request/response schemas
- `app/api/` — Route handlers (async, DB via `Depends(get_db)`)
- `app/services/` — Business logic (scanner, matcher, notifier, ai_assistant)
- `app/tasks/` — Celery tasks (scan_tasks, celery_app config)
- `app/config.py` — `pydantic-settings` loading from `.env`

### Frontend Structure
- `src/pages/` — Route-level components (Dashboard, Boards, Jobs, Applications, Profile, Settings)
- `src/lib/api.ts` — Type-safe REST client organized by resource (`boardsApi`, `jobsApi`, `applicationsApi`, etc.)
- `src/hooks/` — `useWebSocket` (connection manager), `useJobs` (data fetching)
- `src/types/index.ts` — TypeScript interfaces (manually synced with backend Pydantic schemas)
- Path alias: `@/*` → `./src/*`
- Settings stored client-side in localStorage

### Scrapers
All inherit from `BaseScraper` (abstract base in `scrapers/base_scraper.py`) and implement `extract_jobs()` and `go_to_next_page()`. Variants: generic (CSS-selector driven), greenhouse, lever, workday.

## Code Conventions
- Backend: async/await throughout, type hints on all functions, structlog JSON logging
- Frontend: strict TypeScript, functional components, default exports for pages, named exports for API clients
- All Alembic models must be imported in `alembic/env.py` for autogenerate to detect changes
- Alembic uses sync DB URL (strips `+asyncpg` from DATABASE_URL)


## Python & Dependencies
- This project primarily uses Python. Always verify imports work by running the relevant module after changes.
- When fixing import errors, prefer relative imports or proper package structure over sys.path hacks.
- After adding/changing dependencies, update requirements.txt and verify with `pip install -r requirements.txt`.

## Workflow
- When the user asks for a specific tool/approach (e.g., 'make a slash command'), do exactly that — don't substitute with alternatives like Makefiles.
- Before investigating root causes extensively, offer a direct fix first. The user prefers action over analysis.
