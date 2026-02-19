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
        ├── ApplicationsPage.tsx
        ├── ProfilePage.tsx
        └── SettingsPage.tsx
```

---

## Core Files

### `App.tsx`

The root component. Responsible for:

- **Sidebar navigation** — links to all six pages (Dashboard, Boards, Jobs, Applications, Profile, Settings) with active-route highlighting
- **Route definitions** — maps URL paths to page components
- **WebSocket connection** — calls `useWebSocket` hook, displays connection status indicator
- **Notification collection** — listens for WebSocket events and stores recent notifications for the dashboard

---

## Types (`types/index.ts`)

All shared TypeScript interfaces, manually synchronized with the backend Pydantic schemas:

| Interface | Mirrors Backend Schema | Used By |
|---|---|---|
| `Board`, `BoardCreate`, `ScraperConfig` | `schemas/board.py` | BoardsPage |
| `Job`, `JobListResponse`, `JobFilters` | `schemas/job.py` | JobsPage, useJobs |
| `Profile`, `Education`, `WorkExperience` | `schemas/profile.py` | ProfilePage |
| `Application`, `ApplicationLog` | `schemas/application.py` | ApplicationsPage |
| `ApplicationStatus` | `models/application.py` enum | ApplicationsPage |
| `DashboardStats` | `schemas/application.py` | DashboardPage |
| `WSEvent` | (websocket event shape) | useWebSocket, App |

---

## API Client (`lib/api.ts`)

Type-safe wrapper around `fetch` for all backend REST endpoints:

### `boardsApi` — Board CRUD + manual scan trigger
### `jobsApi` — Job listing, filtering, hide, mark read
### `profileApi` — Profile CRUD, resume upload, education/experience entries
### `applicationsApi`
- `list(status?, search?)` — query applications with filters
- `get(id)` — get single application
- `create(data)` — log a new application
- `update(id, data)` — update status or notes
- `delete(id)` — delete application
- `archive(id)` — archive application
- `bulkDelete(ids)` — delete multiple applications
- `dashboard()` — fetch dashboard statistics

---

## Pages (`pages/`)

### `DashboardPage.tsx`

Overview dashboard: stat cards, jobs-by-board bar chart, applications-over-time area chart, recent jobs feed, and activity log.

### `BoardsPage.tsx`

Job board management with card-based layout, add/edit dialogs, keyword management, and scraper configuration.

### `JobsPage.tsx`

Job browser with full-text search, filters (board, score, location, recency), expandable job cards, and "Track Application" action.

### `ApplicationsPage.tsx`

Application tracker:

- **Tab filters** — All, Applied, Interviewing, Offered, Rejected, Withdrawn, Archived
- **Search + sort** — by company, date, status, match score
- **Bulk operations** — select all / bulk delete
- **Quick-add form** — log a manual application with status and notes
- **Expandable detail** — status changer, notes editor, activity log, archive/delete actions
- **Match score** — displays score dot when linked to a job

### `ProfilePage.tsx`

User profile form with personal info, resume upload, job preferences, education, work experience, and EEO fields.

### `SettingsPage.tsx`

Client-side settings in localStorage: notification preferences, scan behavior, data export.
