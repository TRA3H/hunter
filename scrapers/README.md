# Scrapers

Playwright-based web scrapers for extracting job listings from various job board platforms. Each scraper inherits from a common base class and implements platform-specific extraction logic.

## Directory Structure

```
scrapers/
├── __init__.py             # Package init, exports scraper classes
├── utils.py                # Shared utilities (robots.txt, delays, user agents)
├── base_scraper.py         # Abstract base class for all scrapers
├── generic_scraper.py      # CSS selector-driven configurable scraper
├── greenhouse_scraper.py   # Greenhouse ATS scraper
├── lever_scraper.py        # Lever ATS scraper
└── workday_scraper.py      # Workday ATS scraper
```

---

## Files

### `__init__.py`

Package initializer. Exports all scraper classes so the backend can import them with:

```python
from scrapers import GenericScraper, GreenhouseScraper, LeverScraper, WorkdayScraper
```

### `utils.py`

Shared utility functions used by all scrapers:

- **`check_robots_txt(url)`** — fetches and parses `robots.txt` for the given domain. Returns `True` if the `HunterBot` user agent (or `*`) is allowed to access the URL. Scrapers call this before starting to be polite.
- **`random_delay(min_sec, max_sec)`** — async sleep for a random duration (default 2-8 seconds) between page loads to avoid rate limiting and detection.
- **`get_random_user_agent()`** — returns a random browser user agent string from a pool of Chrome, Firefox, Safari, and Edge variants. Rotated per scraper session.
- **`normalize_url(url, base_url)`** — resolves relative URLs against a base URL. Handles protocol-relative (`//`), root-relative (`/`), and already-absolute URLs.

### `base_scraper.py` — `BaseScraper`

Abstract base class that all scrapers extend. Provides the scraping lifecycle:

```
__init__(board_config) → scrape() → [extract_jobs() + go_to_next_page()] per page
```

**`__init__(board_config)`**
Takes the board's `scraper_config` dict (scraper type, selectors, pagination settings, max pages).

**`scrape(url)`** — Main entry point:
1. Launches a headless Chromium browser via Playwright
2. Sets a random user agent
3. Checks `robots.txt` — skips if disallowed
4. Navigates to the URL
5. Loops up to `max_pages` times:
   - Calls `extract_jobs()` to get listings from the current page
   - Calls `go_to_next_page()` to advance
   - Applies `random_delay()` between pages
6. Closes the browser
7. Returns all collected jobs as a list of dicts

**Abstract methods** (subclasses must implement):
- **`extract_jobs(page)`** — given a Playwright `Page`, return a list of job dicts with keys: `title`, `company`, `location`, `url`, `salary`, `posted_date`, `description`
- **`go_to_next_page(page)`** — navigate to the next page of results, return `True` if successful or `False` if no more pages

### `generic_scraper.py` — `GenericScraper`

A fully configurable scraper that uses CSS selectors provided in the board's `scraper_config`. This is the default scraper type and works with most job boards.

**Default selectors** (overridden per board):
- `job_card` — container element for each listing
- `title`, `company`, `location`, `link`, `salary`, `posted_date`, `description` — elements within each card
- `next_page` — pagination button/link

**`extract_jobs(page)`:**
1. Waits for `job_card` selector to appear
2. Queries all matching elements
3. For each card, extracts text content using the configured sub-selectors
4. Normalizes URLs with `utils.normalize_url()`
5. Returns list of job dicts

**`go_to_next_page(page)`:**
Supports three pagination strategies (from `scraper_config.pagination_type`):
- **`click`** — finds the `next_page` selector and clicks it, waits for navigation
- **`url_param`** — appends/increments a page number query parameter
- **`infinite_scroll`** — scrolls to bottom, waits for new content to load

### `greenhouse_scraper.py` — `GreenhouseScraper`

Purpose-built for Greenhouse ATS boards (`boards.greenhouse.io/*`).

**Selectors:** `.opening` for job cards, department grouping via `section.level-0`, job links via `a[href*="/jobs/"]`.

**`extract_jobs(page)`:**
- Greenhouse lists jobs grouped by department
- Extracts department name from section headers as a pseudo-location
- Job titles and URLs from anchor tags within `.opening` elements
- Company name derived from the board URL path

**`go_to_next_page(page)`:**
Returns `False` — Greenhouse boards are single-page listings (all jobs load at once).

### `lever_scraper.py` — `LeverScraper`

Purpose-built for Lever ATS boards (`jobs.lever.co/*`).

**Selectors:** `.posting` for job cards, `[data-qa="posting-name"]` for titles, `.posting-categories` for location/department metadata.

**`extract_jobs(page)`:**
- Each `.posting` element contains the job title, link, and categorized metadata
- Location and team/department extracted from `.posting-categories` child spans
- Company name derived from the board URL

**`go_to_next_page(page)`:**
Returns `False` — Lever boards are single-page listings.

### `workday_scraper.py` — `WorkdayScraper`

Purpose-built for Workday ATS boards (`*.myworkdayjobs.com`). The most complex scraper due to Workday's heavy JavaScript rendering.

**Selectors:** `[data-automation-id="jobTitle"]` with multiple fallback selectors for different Workday layouts.

**`extract_jobs(page)`:**
- Waits extra time for JavaScript to render (Workday is a full SPA)
- Tries multiple selector strategies to find job cards
- Extracts title, company, location, and URL from each card
- Handles Workday's dynamic URL structure

**`go_to_next_page(page)`:**
Supports two strategies:
- "Show More" button click
- Next page arrow/button

Returns `False` when neither pagination element is found.

---

## How Scrapers Connect to the Backend

Scrapers are loaded dynamically by `backend/app/tasks/scan_tasks.py`:

```
1. Celery beat triggers check_scan_schedules() every 60s
2. For each board due for scanning, dispatches scan_board_task(board_id)
3. scan_board_task loads the board's scraper_config from the database
4. _get_scraper_class() maps scraper_type to the right class:
     "generic"    → GenericScraper
     "greenhouse" → GreenhouseScraper
     "lever"      → LeverScraper
     "workday"    → WorkdayScraper
5. Instantiates the scraper with the board's config
6. Calls scraper.scrape(board.url) → returns list of job dicts
7. Filters results by board.keyword_filters
8. Passes to scanner.store_scraped_jobs() for dedup + DB insert
9. Passes to matcher.score_jobs() for scoring against user profile
10. Broadcasts new_job events via WebSocket
```

### Data Flow Diagram

```
JobBoard (DB)
  │
  ├── url ─────────────────► Scraper.scrape(url)
  ├── scraper_config ──────► Scraper.__init__(config)
  └── keyword_filters ─────► Post-scrape filtering
                                    │
                                    ▼
                             List of job dicts:
                             [{title, company, location,
                               url, salary, description}]
                                    │
                                    ▼
                             scanner.store_scraped_jobs()
                             (dedup, parse salary, insert)
                                    │
                                    ▼
                             matcher.score_jobs()
                             (score 0-100 per job)
                                    │
                                    ▼
                             Jobs table (PostgreSQL)
```

---

## Adding a New Scraper

1. Create `scrapers/new_platform_scraper.py`
2. Extend `BaseScraper`, implement `extract_jobs()` and `go_to_next_page()`
3. Export it from `scrapers/__init__.py`
4. Add the scraper type string to `_get_scraper_class()` in `backend/app/tasks/scan_tasks.py`
5. Add the type to `SCRAPER_TYPES` in `frontend/src/pages/BoardsPage.tsx`
6. Add it to the `ScraperConfig.scraper_type` literal in `backend/app/schemas/board.py`
