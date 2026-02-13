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

Loads all configuration from environment variables using `pydantic-settings`. A single `Settings` instance is imported throughout the app. Controls database URL, Redis URL, API keys, email settings, CORS origins, and logging level.

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
3. Mounts `/uploads` as a static file directory (for screenshots)
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

Tracks an auto-apply attempt. Key fields:

- `status` — enum: `pending`, `in_progress`, `needs_review`, `ready_to_submit`, `submitted`, `failed`, `cancelled`
- `form_fields` (JSONB) — detected form fields with values and confidence scores
- `ai_answers` (JSONB) — AI-generated responses to free-text questions
- `screenshot_path` — page screenshot taken during the attempt
- `celery_task_id` — links to the running Celery task

`ApplicationLog` records timestamped status changes for a full audit trail.

---

## Schemas (`app/schemas/`)

Pydantic models for API request validation and response serialization. Each schema file mirrors its corresponding model file:

| File | Key Schemas | Purpose |
|---|---|---|
| `board.py` | `BoardCreate`, `BoardUpdate`, `BoardResponse`, `ScraperConfig` | Board CRUD payloads |
| `job.py` | `JobResponse`, `JobListResponse`, `JobFilters` | Job queries with filtering, pagination, sorting |
| `profile.py` | `ProfileUpdate`, `ProfileResponse`, `EducationCreate`, `WorkExperienceCreate` | Profile management |
| `application.py` | `ApplicationCreate`, `ApplicationReview`, `ApplicationResponse`, `FormField`, `DashboardStats` | Auto-apply and dashboard |

The frontend TypeScript types in `frontend/src/types/index.ts` mirror these schemas (manually synchronized).

---

## API Routes (`app/api/`)

Each file defines a `router` that `main.py` includes.

### `boards.py` — `/api/boards`

Full CRUD for job boards. The `POST /api/boards/{id}/scan` endpoint triggers a manual scan by dispatching `scan_board_task` to Celery. Updates the board's `last_scan_status` to `"running"` immediately so the frontend can show a spinner.

### `jobs.py` — `/api/jobs`

List and filter jobs. The `_build_job_query()` helper constructs a SQLAlchemy query that supports:

- Full-text search via `plainto_tsquery` and `ts_rank` on the `description_tsv` column
- Board filter, score range, location substring, new-only, hidden toggle
- Sorting by `match_score`, `created_at`, or `relevance` (ts_rank)
- Offset/limit pagination

Also provides hide and mark-as-read endpoints.

### `profile.py` — `/api/profile`

Get-or-create pattern: `_get_or_create_profile()` ensures there's always exactly one profile row. Supports resume file upload (saved to `uploads/resumes/`), and CRUD for education and work experience entries.

### `autoapply.py` — `/api/applications`

The most complex router. Key endpoints:

- **`POST /api/applications`** — Kicks off `auto_apply_task` via Celery
- **`POST /api/applications/{id}/review`** — User submits reviewed form fields, dispatches `resume_apply_task`
- **`POST /api/applications/{id}/ai-assist`** — Calls `ai_assistant.generate_answers()` to draft answers for free-text fields
- **`GET /api/applications/dashboard`** — Aggregates stats: board counts, job counts, application status breakdowns, jobs per board, applications over time, and recent activity

### `websocket.py` — `/ws`

Manages real-time communication:

- **`connected_clients`** — global set of active WebSocket connections
- **`websocket_endpoint()`** — accepts connections, keeps alive with ping/pong
- **`broadcast()`** — sends a JSON event to all connected clients
- **`broadcast_sync()`** — publishes to Redis `hunter:ws_broadcast` channel (called from Celery workers which run in a separate process)
- **`ws_listener()`** — background task started on app startup that subscribes to Redis and relays messages to all WebSocket clients

This Redis pub/sub bridge is what allows Celery workers (separate processes) to push real-time updates to the frontend.

---

## Services (`app/services/`)

Business logic separated from route handlers.

### `scanner.py`

Handles storing scraped jobs and deduplication:

- **`compute_dedup_hash()`** — SHA256 from URL (or title+company fallback)
- **`parse_salary()`** — Extracts salary range from text (handles "$120K", "$80,000-$100,000", etc.)
- **`store_scraped_jobs()`** — Bulk inserts new jobs, skips duplicates by hash, returns count of new jobs

### `matcher.py`

Scoring algorithm that rates jobs 0-100 against user preferences:

- **`compute_keyword_score()`** (40% weight) — keyword frequency in description
- **`compute_title_similarity()`** (35% weight) — token overlap with desired job title
- **`compute_location_score()`** (25% weight) — location match with remote preference
- **`compute_match_score()`** — weighted combination
- **`score_jobs()`** — applies scoring to a batch of jobs
- **`fulltext_search()`** — PostgreSQL `ts_rank` based search

### `notifier.py`

Email notifications via Resend API (primary) or SMTP (fallback):

- **`notify_new_jobs()`** — styled HTML email listing new job matches
- **`notify_application_needs_review()`** — alert when an auto-apply pauses for review

### `autofill.py`

Form detection and auto-fill engine using Playwright:

- **`analyze_form_fields()`** — finds all `<input>`, `<select>`, `<textarea>` elements on a page, maps them to profile fields using regex patterns
- **`detect_field_type()`** — pattern matching against labels, names, placeholders, aria-labels
- **`fill_form_fields()`** — types/selects values into detected fields
- **`has_captcha()`** — detects reCAPTCHA, hCaptcha, etc.
- **`needs_human_review()`** — returns true if any field has confidence below threshold (0.7)

`FIELD_PATTERNS` is a dictionary mapping field types (name, email, phone, address, EEO fields) to regex patterns.

### `ai_assistant.py`

Claude API integration for answering free-text application questions. Builds a profile summary as context and asks Claude to draft responses. Used when the user clicks "AI Assist" on a paused application.

---

## Tasks (`app/tasks/`)

Celery task definitions for background processing.

### `celery_app.py`

Configures the Celery instance:

- Broker and result backend: Redis
- JSON serialization
- Time limits: 10 min soft, 15 min hard
- Beat schedule: `check_scan_schedules` runs every 60 seconds

### `scan_tasks.py`

- **`check_scan_schedules()`** — periodic task that queries all enabled boards, checks if `scan_interval_minutes` has elapsed since `last_scanned_at`, and dispatches `scan_board_task` for each
- **`scan_board_task(board_id)`** — loads the board config, instantiates the appropriate scraper, runs it, filters results by keywords, stores via `scanner.store_scraped_jobs()`, scores via `matcher.score_jobs()`, broadcasts `new_job` events via WebSocket, and sends email notifications

### `apply_tasks.py`

- **`auto_apply_task(application_id)`** — launches Playwright, navigates to the job URL, calls `autofill.analyze_form_fields()`, auto-fills what it can, pauses if review needed (CAPTCHA, low-confidence fields)
- **`resume_apply_task(application_id)`** — resumes after user review, fills the reviewed fields, clicks submit
- Both tasks broadcast status updates via `broadcast_sync()` so the frontend updates in real-time

---

## Migrations (`alembic/`)

### `versions/001_initial.py`

Creates all tables: `job_boards`, `jobs`, `user_profiles`, `education`, `work_experience`, `applications`, `application_logs`. Notable:

- GIN index on `jobs.description_tsv` for full-text search performance
- PostgreSQL trigger that auto-updates `description_tsv` on every INSERT/UPDATE
- UUID primary keys on all tables

### `env.py`

Imports all models to register them with SQLAlchemy metadata, then runs Alembic migrations synchronously (strips `+asyncpg` from the database URL).

---

## How It All Connects

```
                  ┌──────────────┐
  HTTP requests   │   main.py    │  Mounts all routers, starts ws_listener
  ──────────────► │   (FastAPI)  │
                  └──────┬───────┘
                         │
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
      api/boards    api/jobs     api/autoapply ──► tasks/apply_tasks
           │             │             │                    │
           │             ▼             ▼                    ▼
           │        services/     services/           services/
           │        matcher      ai_assistant         autofill
           │
           ▼
   tasks/scan_tasks ──► scrapers/* ──► services/scanner ──► services/matcher
           │
           ▼
   services/notifier (email)
           │
           ▼
   api/websocket (Redis pub/sub ──► browser)
```

1. **API routes** receive requests and delegate to services or dispatch Celery tasks
2. **Celery tasks** run long operations (scanning, applying) in worker processes
3. **Services** contain pure business logic, shared between routes and tasks
4. **WebSocket + Redis** bridges the gap between async Celery workers and the frontend

---

## Tests (`tests/`)

Pytest with async support. Unit tests mock Playwright elements; integration tests use an in-memory SQLite database with `@compiles` hooks mapping PostgreSQL types (JSONB, TSVECTOR, UUID) to SQLite equivalents.

### `conftest.py` — Shared Fixtures

Provides reusable test data across all test files:
- **`sample_profile`** — a `UserProfile` instance with realistic fields (name, email, desired title, locations, remote preference, salary)
- **`sample_job`** — a `Job` instance with a full description containing keywords (Python, React, FastAPI, PostgreSQL, Docker)
- **`sample_raw_jobs`** — a list of 3 raw job dicts simulating scraper output (Backend Engineer, Frontend Developer, DevOps Engineer) with varying salary formats and optional fields

### `test_scanner.py` — Dedup Hash + Salary Parsing (15 tests)

Tests the two core scanner utilities:
- **`TestComputeDedupHash`** (6 tests) — verifies URL-based deduplication (same URL = same hash regardless of title/company), URL normalization (trailing slash, case insensitivity), and fallback to title+company hashing when URL is empty
- **`TestParseSalary`** (9 tests) — validates salary string parsing across formats: `$80,000 - $120,000`, `$100K - $150K`, `100k - 150k`, single values, empty strings, non-numeric text ("Competitive"), and `to`/en-dash separators

### `test_matcher.py` — Job Scoring Algorithm (13 tests)

Tests each scoring component and the weighted combination:
- **`TestComputeKeywordScore`** (5 tests) — keyword frequency scoring: 100% when all match, 50% for half, 0% for none, 0% for empty keyword list, case-insensitive matching
- **`TestComputeTitleSimilarity`** (4 tests) — token overlap between job title and desired title: exact match = 100, partial overlap in 50-80 range, no overlap = 0, empty desired = 0
- **`TestComputeLocationScore`** (6 tests) — location matching: "Remote" with remote preference = 100, city substring match = 100, no match = 0, no preference = 50, remote with "any" preference = 100
- **`TestComputeMatchScore`** (3 tests) — end-to-end weighted score (40% keyword + 35% title + 25% location): high match >= 70, low match < 30, score always in 0-100 bounds

### `test_autofill.py` — Form Detection + Profile Mapping (17 tests)

Tests the auto-fill engine's field detection heuristics and profile value extraction:
- **`TestDetectFieldType`** (10 tests) — pattern matching from HTML attributes (tag, type, label, name, placeholder, aria-label) to profile field keys: first_name, email, phone, linkedin_url, us_citizen, sponsorship_needed, resume file upload, veteran_status, gender, and unknown fields below confidence threshold
- **`TestGetProfileValue`** (6 tests) — extracting and formatting profile values: full_name concatenation, email passthrough, boolean→"Yes"/"No" conversion (us_citizen, sponsorship_needed), empty string with 0.0 confidence for missing fields, None boolean handling
- **`TestHasCaptcha`** (5 tests) — CAPTCHA detection in page HTML: reCAPTCHA (`g-recaptcha`), hCaptcha (`h-captcha`), Cloudflare Turnstile (`cf-turnstile`), no false positives on clean forms, detection in `<script>` tags
- **`TestNeedsHumanReview`** (3 tests) — review trigger logic: all "filled" = no review, any "needs_input" = review needed, empty field list = no review

### `test_recent_jobs.py` — Jobs API Integration Tests (10 tests)

Full integration tests against the FastAPI app with an in-memory SQLite database:
- **`TestRecentEndpoint`** (7 tests) — `GET /api/jobs/recent`: default 7-day window, custom `days` param, 30-day window, null `posted_date` exclusion, empty results, pagination (page/page_size), and 422 validation for invalid days (0, -1)
- **`TestPostedDaysFilter`** (3 tests) — `posted_days` query param on `GET /api/jobs`: filters by recency, omitted param returns all jobs, combines correctly with location filter

### `test_scraper_utils.py` — Scraper Shared Utilities (13 tests)

Tests utility functions shared across all scrapers:
- **`TestGetRandomUserAgent`** (2 tests) — returns a string from the USER_AGENTS pool, produces variety over many calls
- **`TestRandomDelay`** (2 tests) — calls `asyncio.sleep` with a value in the specified range, default range is 2-8 seconds
- **`TestCheckRobotsTxt`** (4 tests) — robots.txt compliance: allowed when `Allow: /`, blocked when `Disallow: /` for HunterBot, 404 returns allowed (assume no restrictions), network errors return allowed (fail open)
- **`TestExtractDomain`** (5 tests) — domain extraction from URLs: simple, with port, with subdomain, HTTP scheme, with query params
- **`TestNormalizeUrl`** (5 tests) — URL resolution: absolute returned as-is, protocol-relative (`//`), root-relative (`/path`), relative path with and without trailing slash on base

### `test_generic_scraper.py` — Generic CSS Scraper (14 tests)

Tests the configurable CSS selector-driven scraper:
- **`TestInstantiation`** (4 tests) — default config values, custom selector merging (overrides only specified keys, keeps defaults for rest), custom pagination type, None selectors fallback
- **`TestExtractJobs`** (4 tests) — single job extraction with all fields, multiple jobs, skipping cards without title, custom selector usage verification
- **`TestExtractJobsEmpty`** (1 test) — empty result when both primary and fallback selectors return nothing (verifies double query_selector_all call)
- **`TestPaginateClick`** (4 tests) — click pagination: enabled next button clicks and waits, disabled attribute stops pagination, "disabled" CSS class stops pagination, missing button returns false
- **`TestPaginateScroll`** (2 tests) — infinite scroll: height change = more content, unchanged height = end of results
- **`TestPaginateUrl`** (2 tests) — URL param pagination falls back to click behavior, unknown pagination type returns false

### `test_lever_scraper.py` — Lever ATS Scraper (12 tests)

Tests the Lever job board scraper with mocked Playwright elements:
- **`TestImportAndInstantiation`** (3 tests) — import works, base_url set, inherits BaseScraper
- **`TestExtractJobsStandardPostings`** (4 tests) — standard `.posting` elements with title/link/location/team/commitment, postings missing optional fields, title fallback to anchor text, href fallback to `evaluate()`
- **`TestExtractJobsFallbackToLinks`** (3 tests) — fallback to `a[href*="/jobs/"]` links when no `.posting` elements found, short titles (<=3 chars) filtered out, exception handling skips bad links
- **`TestExtractJobsNoPostings`** (1 test) — all selectors empty = empty result
- **`TestCompanyNameExtraction`** (2 tests) — company from page header applied to all jobs, missing company element = empty string
- **`TestGoToNextPage`** (2 tests) — always returns false (Lever is single-page)

### `test_workday_scraper.py` — Workday ATS Scraper (14 tests)

Tests the Workday job board scraper (the most complex due to Workday's JS-heavy rendering):
- **`TestExtractJobs`** (8 tests) — card extraction with anchor tags, non-anchor tag handling (falls back to nested `a`), empty results, skipping cards without href or title, fallback selector strategy, timeout resilience, company name applied to all jobs, exception in one card doesn't break others
- **`TestGoToNextPage`** (6 tests) — "Show More" button click, disabled Show More falls through, next arrow button click, disabled next arrow, no pagination buttons, exception returns false
- **`TestInstantiation`** (3 tests) — import and creation, custom config (max_pages), inherits BaseScraper

### `test_greenhouse_scraper.py` — Greenhouse ATS Scraper (14 tests)

Tests the Greenhouse job board scraper:
- **`TestInstantiation`** (4 tests) — inherits BaseScraper, base_url set, default config, custom config
- **`TestExtractJobsStandardSections`** (5 tests) — single job from section, multiple jobs, no location element, section without link skipped, secondary selector fallback when primary empty
- **`TestExtractJobsFallbackLinks`** (5 tests) — fallback to `a[href*="/jobs/"]` links, fallback jobs have empty non-title fields, empty title skipped, no href skipped, exception in one link doesn't break others
- **`TestExtractJobsEmpty`** (1 test) — no jobs found = empty list
- **`TestCompanyNameExtraction`** (4 tests) — company applied to all section jobs, no company element = empty, whitespace-only company = empty, company not applied for fallback link path
- **`TestGoToNextPage`** (2 tests) — always returns false (Greenhouse is single-page)

### Running Tests

```bash
cd backend && pytest tests/ -v
```

**Note:** Scraper tests (test_generic_scraper, test_lever_scraper, etc.) require `playwright` Python package installed. Integration tests (test_recent_jobs) require `aiosqlite` and `httpx`. Neither requires a running PostgreSQL or Redis instance.
