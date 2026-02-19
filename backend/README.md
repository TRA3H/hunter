# Backend

FastAPI application server, Celery task workers, and all business logic. Python 3.12, fully async.

## Directory Structure

```
backend/
├── Dockerfile              # Playwright-based Python image
├── requirements.txt        # Python dependencies
├── alembic.ini             # Alembic migration config
├── alembic/                # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial.py
├── app/
│   ├── __init__.py
│   ├── config.py           # Settings from environment
│   ├── database.py         # SQLAlchemy async engine + session
│   ├── main.py             # FastAPI app entry point
│   ├── models/             # SQLAlchemy ORM models
│   ├── schemas/            # Pydantic request/response schemas
│   ├── api/                # Route handlers
│   ├── services/           # Business logic
│   └── tasks/              # Celery task definitions
└── tests/
```

---

## Core Files

### `app/config.py`

Loads all configuration from environment variables using `pydantic-settings`. A single `Settings` instance is imported throughout the app. Controls database URL, Redis URL, API keys, email settings, CORS origins, logging level, and AI model selection (`ANTHROPIC_MODEL`).

### `app/database.py`

Sets up the async SQLAlchemy engine (PostgreSQL + `asyncpg`) and the session factory. Exports:

- **`engine`** — async connection pool
- **`async_session_factory`** — creates `AsyncSession` instances
- **`Base`** — declarative base that all models inherit from
- **`get_db()`** — FastAPI dependency that yields a session per request

Every API route and service that touches the database gets its session from `get_db()`.

### `app/main.py`

The FastAPI application entry point. On startup it:

1. Configures structured logging via `structlog`
2. Adds CORS middleware (origins from `config.py`)
3. Mounts `/uploads` as a static file directory
4. Includes all API routers under `/api`
5. Starts the WebSocket Redis listener as a background task

---

## Models (`app/models/`)

ORM models map directly to PostgreSQL tables. All use UUID primary keys.

### `board.py` — `JobBoard`

Represents a configured job board to scan. Key fields:

- `name`, `url`, `enabled` — board identity and toggle
- `scan_interval_minutes` — how often Celery should scan
- `keyword_filters` (JSONB `string[]`) — only keep jobs matching these keywords
- `scraper_config` (JSONB) — scraper type, CSS selectors, pagination config
- `last_scanned_at`, `last_scan_status`, `last_scan_error` — scan state tracking

**Relationship:** one-to-many with `Job`.

### `job.py` — `Job`

A discovered job listing. Key fields:

- `title`, `company`, `location`, `url`, `description` — listing data
- `salary_min`, `salary_max` — parsed salary range
- `match_score` (0-100) — computed by the matcher service
- `description_tsv` — PostgreSQL `tsvector` column with a GIN index and auto-update trigger for full-text search
- `dedup_hash` — SHA256 for deduplication across scans
- `is_new`, `is_hidden` — UI state flags

**Relationships:** belongs to `JobBoard`, one-to-many with `Application`.

### `profile.py` — `UserProfile`, `Education`, `WorkExperience`

Single user profile (auto-created on first GET). Stores personal info, contact details, EEO fields, resume path, and job preferences (desired title, locations, remote preference, minimum salary). `Education` and `WorkExperience` are child tables with foreign keys back to the profile.

### `application.py` — `Application`, `ApplicationLog`

Tracks job applications through their lifecycle. Key fields:

- `status` — enum: `applied`, `interviewing`, `offered`, `rejected`, `withdrawn`, `archived`
- `notes` — free-text notes (interview dates, contact info, etc.)
- `applied_via` — how the application was logged (`manual` or `extension`)

`ApplicationLog` records timestamped status changes for a full activity trail.

---

## Schemas (`app/schemas/`)

Pydantic models for API request validation and response serialization:

| File | Key Schemas | Purpose |
|---|---|---|
| `board.py` | `BoardCreate`, `BoardUpdate`, `BoardResponse`, `ScraperConfig` | Board CRUD payloads |
| `job.py` | `JobResponse`, `JobListResponse`, `JobFilters` | Job queries with filtering, pagination, sorting |
| `profile.py` | `ProfileUpdate`, `ProfileResponse`, `EducationCreate`, `WorkExperienceCreate` | Profile management |
| `application.py` | `ApplicationCreate`, `ApplicationUpdate`, `ApplicationResponse`, `BulkDeleteRequest`, `DashboardStats` | Application tracking and dashboard |

The frontend TypeScript types in `frontend/src/types/index.ts` mirror these schemas (manually synchronized).

---

## API Routes (`app/api/`)

Each file defines a `router` that `main.py` includes.

### `boards.py` — `/api/boards`

Full CRUD for job boards. The `POST /api/boards/{id}/scan` endpoint triggers a manual scan by dispatching `scan_board_task` to Celery.

### `jobs.py` — `/api/jobs`

List and filter jobs. Supports full-text search, board filter, score range, location, sorting, and pagination. Also provides hide and mark-as-read endpoints.

### `profile.py` — `/api/profile`

Get-or-create pattern: `_get_or_create_profile()` ensures there's always exactly one profile row. Supports resume file upload and CRUD for education and work experience entries.

### `applications.py` — `/api/applications`

Application tracker endpoints:

- **`GET /api/applications`** — List with optional status and search filters
- **`POST /api/applications`** — Log a new application (optionally linked to a job)
- **`PATCH /api/applications/{id}`** — Update status or notes (with activity logging)
- **`DELETE /api/applications/{id}`** — Hard delete
- **`POST /api/applications/{id}/archive`** — Set status to archived
- **`POST /api/applications/bulk-delete`** — Delete multiple applications
- **`GET /api/applications/dashboard`** — Dashboard statistics (board counts, job counts, applications by status, trends)

### `websocket.py` — `/ws`

Manages real-time communication via Redis pub/sub bridge, allowing Celery workers to push updates to the frontend.

---

## Services (`app/services/`)

Business logic separated from route handlers.

### `scanner.py`

Handles storing scraped jobs and deduplication via SHA256 content hash.

### `matcher.py`

Scoring algorithm that rates jobs 0-100 against user preferences (40% keyword, 35% title similarity, 25% location).

### `notifier.py`

Email notifications via Resend API (primary) or SMTP (fallback).

### `ai_assistant.py`

Claude API integration for generating answers to application questions. Model configurable via `ANTHROPIC_MODEL` setting.

---

## Tasks (`app/tasks/`)

### `celery_app.py`

Configures the Celery instance with Redis broker, JSON serialization, and beat schedule.

### `scan_tasks.py`

- **`check_scan_schedules()`** — periodic task checking which boards need scanning
- **`scan_board_task(board_id)`** — runs scraper, stores jobs, scores matches, broadcasts events

---

## Migrations (`alembic/`)

### `versions/001_initial.py`

Creates all tables with UUID primary keys, GIN index on `jobs.description_tsv`, and auto-update trigger for full-text search.

---

## Tests (`tests/`)

Pytest with async support. Unit tests mock Playwright; integration tests use in-memory SQLite with PG type compatibility hooks.

```bash
cd backend && pytest tests/ -v
```

No running PostgreSQL or Redis required.
