# Hunter Chrome Extension — Architecture

Browser extension for logging job applications directly from job posting sites.

## Structure

```
extension/
├── manifest.json       # MV3 config, permissions for localhost:8000
├── background.js       # Service worker — API communication with Hunter backend
├── content-script.js   # Injected into job sites — detects job pages, provides UI overlay
├── popup.html          # Extension popup — connection status, quick actions
├── popup.js            # Popup logic
└── icons/              # Extension icons (16, 48, 128px)
```

## Manifest V3

Required for Chrome Web Store submission. Also compatible with Firefox 109+.

```json
{
  "manifest_version": 3,
  "name": "Hunter — Job Application Tracker",
  "version": "0.1.0",
  "permissions": ["activeTab", "storage"],
  "host_permissions": ["http://localhost:8000/*"],
  "background": { "service_worker": "background.js" },
  "content_scripts": [{
    "matches": ["*://*.greenhouse.io/*", "*://*.lever.co/*", "*://*.workday.com/*"],
    "js": ["content-script.js"]
  }],
  "action": { "default_popup": "popup.html" }
}
```

## Communication Architecture

```
[Job Site Page]
    │
    ├── content-script.js (injected)
    │   ├── Detects job posting metadata (title, company, URL)
    │   ├── Renders floating "Log Application" button
    │   └── Sends messages to service worker via chrome.runtime.sendMessage()
    │
    ▼
[Service Worker — background.js]
    │
    ├── Receives messages from content script
    ├── Fetches user profile: GET /api/profile
    ├── Creates applications: POST /api/applications { job_id?, applied_via: "extension" }
    ├── Caches profile data in chrome.storage.local
    └── Returns success/failure to content script
    │
    ▼
[Hunter Backend — localhost:8000]
```

Content scripts cannot directly `fetch()` to localhost due to page CSP restrictions. The service worker handles all API communication.

## Key Behaviors

- **"Log Application" button**: Floating overlay on supported job sites. Clicking logs the application to Hunter with `applied_via: "extension"`.
- **Popup**: Shows connection status (green/red dot), recent applications count, link to open Hunter dashboard.
- **Graceful offline**: If the Hunter backend is unreachable, queue the application in `chrome.storage.local` and sync when reconnected.
- **No form filling**: The extension only *logs* applications, it does not auto-fill or submit forms.

## API Integration

| Action | Endpoint | Notes |
|--------|----------|-------|
| Check connection | `GET /api/profile` | Also fetches user name for display |
| Log application | `POST /api/applications` | `{ applied_via: "extension", notes: "Logged via extension" }` |
| Check if already applied | `GET /api/applications?job_id={id}` | Prevent duplicate logging |

## Future Considerations

- Match the current page URL against stored jobs to auto-link `job_id`
- Support additional job boards via configurable URL patterns
- Optional: detect form fields for assisted (not automatic) filling
