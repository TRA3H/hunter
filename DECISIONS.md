# DECISIONS.md — Date Clarity Feature

Assumptions and design decisions made during implementation.

## 1. `posted_date` already existed

The `Job` model already had a `posted_date` column (`DateTime(timezone=True), nullable`). Rather than adding a redundant normalized field, I reused this column and added a B-tree index (`ix_jobs_posted_date`) to speed up range queries.

**Migration:** `002_add_posted_date_index.py` adds the index only.

## 2. `GET /api/jobs/recent?days=7`

- Dedicated endpoint that filters by `posted_date >= now() - N days`.
- Defaults to 7 days, accepts `days` param (1–365).
- Sorted by `posted_date DESC` by default.
- Returns the same `JobListResponse` shape as `GET /api/jobs` (paginated, enriched with board name and application status).
- Jobs with `posted_date = NULL` are excluded from `/recent` results (they have no known post date).

## 3. `posted_days` filter on `GET /api/jobs`

In addition to the dedicated `/recent` endpoint, I added `posted_days` as an optional query param on the main `GET /api/jobs` listing. This allows the frontend filter panel to use the existing `useJobs` hook without a second API client method.

## 4. Frontend recency filter

- Added a "Posted within" `<select>` dropdown to the existing filters panel with options: Any time, Today, Last 3 days, Last 7 days, Last 2 weeks, Last 30 days.
- Uses `data-testid="recency-filter"` for Playwright targeting.
- The "Reset all filters" button clears this filter too.
- No separate API client method was needed — `posted_days` flows through the existing `jobsApi.list()` params.

## 5. Test strategy

**Pytest integration tests** (`tests/test_recent_jobs.py`):
- Uses SQLite + aiosqlite in-memory DB to avoid requiring PostgreSQL for CI.
- Registers `@compiles` hooks to map `JSONB → TEXT`, `TSVECTOR → TEXT`, `UUID → VARCHAR(36)` for SQLite compatibility.
- Overrides FastAPI's `get_db` dependency to use the test session.
- 10 tests covering: default/custom days, null dates, empty results, pagination, validation, combined filters.

**Playwright E2E test** (`frontend/e2e/recency-filter.spec.ts`):
- Tests filter visibility, option values, API request params on selection, and reset behavior.
- Requires running backend + frontend (not run in this session as services are down).

## 6. Pre-existing issues (not addressed)

- `test_matcher.py::TestComputeLocationScore::test_no_match` fails — pre-existing bug in location scoring.
- `tsc --noEmit` shows `import.meta.env` errors — pre-existing, needs `vite/client` types.
- Several test files can't import without `playwright` Python package installed — pre-existing dep issue in CI.
