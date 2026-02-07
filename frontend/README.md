# Frontend

React 18 single-page application built with TypeScript, Vite, Tailwind CSS, and shadcn/ui.

## Directory Structure

```
frontend/
├── Dockerfile              # Node 20 Alpine image
├── package.json            # Dependencies and scripts
├── tsconfig.json           # TypeScript config
├── vite.config.ts          # Vite dev server + proxy config
├── tailwind.config.ts      # Tailwind theme
├── postcss.config.js       # PostCSS plugins
├── index.html              # HTML entry point
└── src/
    ├── main.tsx            # React DOM mount
    ├── App.tsx             # Root component, routing, navigation
    ├── index.css           # Global styles + Tailwind directives
    ├── types/
    │   └── index.ts        # Shared TypeScript interfaces
    ├── lib/
    │   ├── api.ts          # REST API client
    │   └── utils.ts        # Helper functions
    ├── hooks/
    │   ├── useWebSocket.ts # WebSocket connection manager
    │   └── useJobs.ts      # Jobs data fetching hook
    ├── components/
    │   └── ui/             # shadcn/ui primitives
    └── pages/
        ├── DashboardPage.tsx
        ├── BoardsPage.tsx
        ├── JobsPage.tsx
        ├── AutoApplyPage.tsx
        ├── ProfilePage.tsx
        └── SettingsPage.tsx
```

---

## Core Files

### `main.tsx`

Mounts the React app into `#root` with `React.StrictMode` and `BrowserRouter` from react-router-dom.

### `App.tsx`

The root component. Responsible for:

- **Sidebar navigation** — links to all six pages (Dashboard, Boards, Jobs, Auto-Apply, Profile, Settings) with active-route highlighting
- **Route definitions** — maps URL paths to page components
- **WebSocket connection** — calls `useWebSocket` hook, displays connection status indicator (green dot = connected)
- **Notification collection** — listens for WebSocket events and stores recent notifications for the dashboard

### `index.css`

Tailwind CSS directives (`@tailwind base/components/utilities`) plus CSS custom properties for the shadcn/ui theme (colors, border radius, etc.).

---

## Types (`types/index.ts`)

All shared TypeScript interfaces, manually synchronized with the backend Pydantic schemas:

| Interface | Mirrors Backend Schema | Used By |
|---|---|---|
| `Board`, `BoardCreate`, `ScraperConfig` | `schemas/board.py` | BoardsPage |
| `Job`, `JobListResponse`, `JobFilters` | `schemas/job.py` | JobsPage, useJobs |
| `Profile`, `Education`, `WorkExperience` | `schemas/profile.py` | ProfilePage |
| `Application`, `ApplicationLog`, `FormField` | `schemas/application.py` | AutoApplyPage |
| `ApplicationStatus` | `models/application.py` enum | AutoApplyPage |
| `DashboardStats` | `schemas/application.py` | DashboardPage |
| `WSEvent` | (websocket event shape) | useWebSocket, App |

---

## API Client (`lib/api.ts`)

Type-safe wrapper around `fetch` for all backend REST endpoints. Organized into four objects:

### `boardsApi`
- `list()` — GET `/api/boards`
- `get(id)` — GET `/api/boards/{id}`
- `create(data)` — POST `/api/boards`
- `update(id, data)` — PUT `/api/boards/{id}`
- `delete(id)` — DELETE `/api/boards/{id}`
- `scan(id)` — POST `/api/boards/{id}/scan`

### `jobsApi`
- `list(filters)` — GET `/api/jobs` with query parameters
- `get(id)` — GET `/api/jobs/{id}`
- `hide(id)` — PATCH `/api/jobs/{id}/hide`
- `markRead(id)` — PATCH `/api/jobs/{id}/read`

### `profileApi`
- `get()` / `update(data)` — profile CRUD
- `uploadResume(file)` — POST multipart form data
- `addEducation(data)` / `deleteEducation(id)` — education entries
- `addExperience(data)` / `deleteExperience(id)` — work experience entries

### `applicationsApi`
- `list(status?)` / `get(id)` — query applications
- `create(data)` — start auto-apply
- `review(id, data)` — submit reviewed form fields
- `cancel(id)` — cancel application
- `aiAssist(id)` — request AI-generated answers
- `dashboard()` — fetch dashboard statistics

**Base URL** is resolved from `import.meta.env.VITE_API_URL` (defaults to same origin). In development, Vite proxies `/api` and `/ws` to `localhost:8000` (see `vite.config.ts`).

---

## Utilities (`lib/utils.ts`)

Helper functions used across pages:

- **`cn()`** — merges Tailwind classes with `clsx` + `tailwind-merge` (standard shadcn/ui pattern)
- **`formatDate()`** — localized date string
- **`formatRelativeTime()`** — "2 hours ago", "just now", etc.
- **`formatSalary()`** — currency formatting ($80,000 - $120,000)
- **`scoreColor()` / `scoreBgColor()`** — returns Tailwind color classes based on match score (green for high, yellow for medium, red for low)
- **`statusColor()`** — maps application status to badge colors

---

## Hooks (`hooks/`)

### `useWebSocket.ts`

Manages a persistent WebSocket connection to `ws://localhost:8000/ws`:

- **Auto-reconnect** — retries with backoff on disconnect
- **Heartbeat** — sends ping frames to detect stale connections
- **Event callback** — passes parsed `WSEvent` objects to a handler function
- **Connection state** — exposes `isConnected` boolean for UI indicators

Used in `App.tsx` to receive real-time events (`new_job`, `application_update`, `scan_error`).

### `useJobs.ts`

Data fetching hook for the jobs listing page:

- Manages `jobs[]`, `total`, `page`, `filters`, `loading`, `error` state
- **`updateFilters()`** — merges partial filter updates, resets to page 1
- **`refresh()`** — re-fetches current page
- Automatically re-fetches when filters or page change

Used exclusively by `JobsPage.tsx`.

---

## Pages (`pages/`)

### `DashboardPage.tsx`

Overview dashboard showing:

- **Stat cards** — active boards, new jobs today, in-progress applications, submitted count
- **Bar chart** — jobs per board (Recharts `BarChart`)
- **Area chart** — applications over time (Recharts `AreaChart`)
- **Recent jobs feed** — latest discovered jobs with scores
- **Activity log** — recent application status changes

Fetches data from `applicationsApi.dashboard()`. Also displays real-time WebSocket notifications passed down from `App.tsx`.

### `BoardsPage.tsx`

Job board management with a card-based layout:

- **Board cards** — show name, URL, scan interval, keyword badges, last scan status/time
- **Add/Edit dialog** — `BoardForm` component with fields for name, URL, scan interval, scraper type, pagination type, max pages, CSS selectors, and keyword filters
- **Keyword management** — text input to add one at a time, "Import" button to bulk-import from a `.txt`/`.csv` file (splits by newlines and commas, deduplicates)
- **Selector management** — key/value pairs for CSS selectors
- **Actions** — enable/disable toggle, manual scan trigger, edit, delete with confirmation

The `BoardForm` component handles both create and edit modes, pre-populating fields when editing.

### `JobsPage.tsx`

Job browser with filtering and search:

- **Search bar** — full-text search with debouncing (waits 300ms after typing stops)
- **Filter panel** — board dropdown, minimum score slider, location text, new-only toggle, sort options (score, date, relevance)
- **Job cards** — expandable cards showing title, company, location, salary, score badge, posted date. Expanding reveals the full description
- **Actions per job** — Mark as Read, Hide, Auto-Apply button
- **Pagination** — offset/limit with page navigation

Uses the `useJobs` hook for all data management.

### `AutoApplyPage.tsx`

Application tracking and review interface:

- **Application list** — filterable by status (all, needs review, in progress, submitted, failed)
- **Application detail** — expandable card showing job info, current status, screenshot preview, form fields with values and confidence indicators
- **Review mode** — when status is `needs_review`, shows editable form fields, AI Assist button, and Submit/Cancel actions
- **AI Assist** — calls `applicationsApi.aiAssist()` to populate free-text fields with AI-generated answers
- **Audit log** — timeline of status changes with timestamps

### `ProfilePage.tsx`

User profile form:

- **Personal info** — name, email, phone, address fields
- **Resume upload** — file picker for PDF upload
- **Job preferences** — desired title, locations, remote preference, minimum salary
- **Education** — add/remove education entries (school, degree, field, dates)
- **Work experience** — add/remove entries (company, title, dates, description)
- **EEO fields** — optional demographic fields for application auto-fill

Auto-creates the profile on first visit (GET endpoint creates if not exists).

### `SettingsPage.tsx`

Client-side settings stored in `localStorage`:

- **Notification preferences** — email notifications toggle, WebSocket notifications toggle
- **Display settings** — theme preference, jobs per page, default sort order
- **Danger zone** — clear all settings

No backend interaction — purely client-side persistence.

---

## UI Components (`components/ui/`)

Standard [shadcn/ui](https://ui.shadcn.com/) primitives built on Radix UI:

| Component | File | Usage |
|---|---|---|
| `Button` | `button.tsx` | Actions, form submits, navigation |
| `Card` | `card.tsx` | Content containers on every page |
| `Input` | `input.tsx` | Text inputs in forms |
| `Textarea` | `textarea.tsx` | Multi-line text (profile, review) |
| `Badge` | `badge.tsx` | Status labels, keyword tags, score indicators |
| `Dialog` | `dialog.tsx` | Modal forms (add/edit board, confirmations) |

These are not custom components — they follow the shadcn/ui copy-paste pattern and use Radix UI under the hood.

---

## Build & Dev Configuration

### `vite.config.ts`

- **Path alias:** `@` maps to `./src` for clean imports
- **Dev proxy:** `/api`, `/ws`, and `/uploads` are proxied to `http://localhost:8000` so the frontend can call the backend without CORS issues during development
- **WebSocket proxy:** `/ws` is proxied with `ws: true` for WebSocket upgrade

### `tailwind.config.ts`

Extends the default Tailwind theme with CSS custom properties for the shadcn/ui color system. Content paths include `./src/**/*.{ts,tsx}`.

### `Dockerfile`

Node 20 Alpine image. Runs `npm install`, copies source, and starts the Vite dev server on port 5173.

---

## How It All Connects

```
Browser
  │
  ├── App.tsx
  │     ├── useWebSocket ──── ws://backend:8000/ws ──── real-time events
  │     └── Routes
  │           ├── DashboardPage ──── applicationsApi.dashboard()
  │           ├── BoardsPage ─────── boardsApi.*()
  │           ├── JobsPage ──────── useJobs ──── jobsApi.list()
  │           ├── AutoApplyPage ──── applicationsApi.*()
  │           ├── ProfilePage ────── profileApi.*()
  │           └── SettingsPage ───── localStorage
  │
  └── lib/api.ts ──── fetch("/api/*") ──── Vite proxy ──── FastAPI backend
```

1. `App.tsx` establishes the WebSocket connection and renders the active page
2. Each page calls `lib/api.ts` functions which hit the backend REST API
3. Real-time updates (new jobs, application status changes) arrive via WebSocket and trigger UI refreshes
4. Types in `types/index.ts` keep the frontend in sync with backend response shapes
