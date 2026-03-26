# Chronicler Web UI — Design Spec

## Overview

A local web dashboard for Chronicler that lets users monitor watched projects, manage project setup, browse the full change log, and generate handoff documents — all from a browser UI. Designed for non-developer users who code with AI tools.

Launched via `chronicler ui`, served on `localhost:8765`, auto-opens the browser.

---

## Goals

- **See what's happening**: live activity feed updating the instant a file is saved
- **Manage projects**: add, start, stop, and configure watched projects from the UI
- **Traffic lights**: immediate visual status for each project (running / stopped / error)
- **Full log access**: searchable, filterable, session-grouped log per project
- **Generate handoffs**: one-click handoff generation from the UI
- **Non-developer friendly**: clear onboarding, plain-English tooltips, no jargon

---

## Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Web server | FastAPI | Async Python, native SSE support, fits existing stack |
| Frontend | Single HTML file — Alpine.js + Tailwind CSS via CDN | No build step, no npm, reactive UI, polished look |
| Real-time | Server-Sent Events (SSE) | Push new log entries to browser the instant they're written to SQLite |
| New deps | `fastapi`, `uvicorn` | Pure Python, pip-installable |

---

## File Structure

```
chronicler/ui/
├── __init__.py
├── server.py          # FastAPI app — all routes + SSE stream
└── static/
    └── index.html     # Single-page app (Alpine.js + Tailwind via CDN)
```

New CLI command added to `chronicler/cli/main.py`:

```bash
chronicler ui              # starts server on localhost:8765, opens browser
chronicler ui --port 9000  # custom port
chronicler ui --no-open    # start server without opening browser
```

---

## Backend API

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Serve `index.html` |
| GET | `/api/projects` | All projects with daemon status (running/stopped/error) |
| POST | `/api/projects` | Add a new project (runs init logic: create `.chronicler/`, register in DB) |
| POST | `/api/projects/{id}/start` | Start daemon for project |
| POST | `/api/projects/{id}/stop` | Stop daemon for project |
| GET | `/api/activity` | Recent log entries. Optional: `?project_id=`, `?change_type=`, `?limit=` |
| GET | `/api/activity/stream` | SSE stream — pushes new `log_entries` rows as they're inserted |
| POST | `/api/projects/{id}/handoff` | Generate handoff doc, return markdown |
| GET | `/api/projects/{id}/map` | Return current `CHRONICLER_MAP.md` content |

### Real-time flow

```
File saved → watcher → SQLite insert → SSE endpoint detects new row → pushes to browser → feed updates
```

The SSE endpoint polls for `log_entries` rows with `id > last_sent_id` on a short interval (e.g. 1s). On new rows, pushes them as JSON events. The browser appends entries to the top of the feed with a fade-in animation.

---

## Dashboard Layout

**Layout: Cards + Unified Feed (always-visible split)**

```
┌─────────────────────────────────────────────────────────┐
│  Chronicler v0.1.0                          ● Live       │  ← top bar
├──────────────────────┬──────────────────────────────────┤
│  PROJECTS        + Add│  ACTIVITY  [All][feature][bug].. │
│                      │                       ✦ Handoff  │
│  ● Macro    nextjs   │  M 03:27  feature  Added ttl_days │
│    14 changes · 3 ses│  A 03:10  feature  Auth middleware│
│    [View map][Handoff]│  M 03:17  refactor LLM selection │
│                      │                                  │
│  ○ chronicler python │  ── Full Log ──────────────────  │
│    0 changes today   │  [searches + filters + sessions]  │
│                      │                                  │
│  ● autark-web react  │                                  │
│    8 changes today   │                                  │
│                      │                                  │
│  + Add project       │                                  │
└──────────────────────┴──────────────────────────────────┘
```

### Left panel — Project cards

Each card shows:
- **Traffic light dot** (green = running, grey = stopped, red = error) — clickable to start/stop. Tooltip: "Watching for changes — click to stop" / "Not watching — click to start"
- Project name + detected framework badge
- Stats: changes today, session count, time active
- Action buttons: **View map** (opens CHRONICLER_MAP.md in a modal), **Handoff ✦** (generates handoff for this project)
- **+ Add project** button at the bottom

### Right panel — Activity + Full Log tabs

**Activity tab (default):**
- Live feed of recent entries across all watched projects
- Each entry shows: colour-coded project initial (M / A / C), change type badge, impact dot, relative time, file path, LLM summary
- Filter pills: All / feature / bug fix / refactor / config / dependency / delete
- **✦ Generate Handoff** button (top right) — generates across all active projects
- New entries animate in at the top (fade + slide)

**Full Log tab:**
- Searchable (free text against file path + summary)
- Filterable by change type and date range
- Grouped by session (session header shows date range + session health label: `productive` / `debugging` / `exploratory` / `maintenance`)
- Each entry shows: full timestamp (`2026-03-26 03:27:16`), change type badge, impact level, file path, summary
- Expandable diff inline (click to reveal the actual code change)
- Per-project filter (dropdown at top)

---

## Onboarding Flow

Shown on first launch (no projects registered). A modal overlay with 4 steps, progress bar across the top.

### Step 1 — Welcome
Plain-English explanation: what Chronicler does, that it works silently in the background, no coding knowledge required. CTA: "Get started →"

### Step 2 — Add your first project
- Folder path input + "Browse…" button (opens native file picker via `<input type="file" webkitdirectory>`)
- Project name input (auto-filled from folder name)
- Auto-detects framework on path selection, shows "✓ Next.js project detected" pill
- "I'll do this later" skip link

### Step 3 — Connect your AI key
- Explains Groq is free, no credit card needed
- If `GROQ_API_KEY` is already set in the environment, shows "✓ API key detected — you're all set" and auto-advances
- Otherwise: text input for key + link to `console.groq.com`
- "Skip — I'll add it later" link

### Step 4 — Done
- Checklist confirming what's set up
- Two key hints: how to add more projects, how to generate a handoff
- "Open dashboard →" closes the modal

---

## Contextual Help

Everywhere in the UI:
- **Tooltips** on all action buttons (hover reveals plain-English explanation)
- **Empty states** with actionable guidance (e.g. "No changes logged yet — start coding and Chronicler will pick them up automatically")
- **Top bar hint** on the dashboard: rotates through the 2-3 most useful tips (e.g. "Click the coloured dot to start or stop watching a project")
- **Handoff button tooltip**: "Creates a briefing document so your AI coding assistant knows exactly where to pick up"

---

## Daemon Status

Projects show one of three states:

| State | Colour | Meaning |
|-------|--------|---------|
| running | Green (●) | Watcher process is active |
| stopped | Grey (●) | Watcher not running |
| error | Red (●) | Watcher crashed or API key missing |

The `/api/projects` endpoint checks whether a PID file exists and the process is alive for each project. Status refreshes every 5 seconds via a lightweight poll (not SSE — SSE is reserved for activity entries only).

---

## Scope (v1)

**In scope:**
- `chronicler ui` CLI command
- FastAPI server + static HTML frontend
- All routes listed above
- Dashboard (project cards + activity feed + full log tab)
- Onboarding flow (4 steps)
- Contextual tooltips + empty states
- SSE live feed
- Generate handoff from UI

**Out of scope (future):**
- macOS menubar/tray integration
- Config editing from the UI
- Dark/light theme toggle
- Multi-user / remote access
- Session detail view (beyond log grouping)
