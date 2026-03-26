# Chronicler Web UI — Design Spec

## Overview

A local web dashboard for Chronicler that lets users monitor watched projects, manage project setup, browse the full change log, and generate handoff documents — all from a browser UI. Designed for non-developer users who code with AI tools.

Launched via `chronicler ui`, served on `localhost:8765`, auto-opens the browser.

---

## Goals

- **See what's happening**: live activity feed updating the instant a file is saved
- **Manage projects**: add, start, stop, and configure watched projects from the UI
- **Traffic lights**: immediate visual status for each project (running / stopped)
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

**Server lifecycle:** Runs in the foreground (blocking, Ctrl-C to stop). No PID file needed. If the port is already in use, print a clear message and exit: `"Port 8765 is in use. Try: chronicler ui --port 9000"`. The terminal session that launched `chronicler ui` must stay open while the dashboard is in use.

---

## Backend API

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Serve `index.html` |
| GET | `/api/projects` | All projects with daemon status (running/stopped) |
| POST | `/api/projects` | Add a new project (runs init logic — see below) |
| POST | `/api/projects/{id}/start` | Start daemon for project |
| POST | `/api/projects/{id}/stop` | Stop daemon for project |
| GET | `/api/activity` | Recent log entries. Optional: `?project_id=`, `?change_type=`, `?limit=` |
| GET | `/api/activity/stream` | SSE stream — pushes new `log_entries` rows as they're inserted |
| POST | `/api/projects/{id}/handoff` | Generate handoff doc, return markdown |
| GET | `/api/projects/{id}/map` | Return current `CHRONICLER_MAP.md` content |
| GET | `/api/detect-framework` | Auto-detect framework from path. Query param: `?path=`. Returns `{ "framework": "nextjs" \| "" }` |
| GET | `/api/config/groq-key-status` | Returns `{ "detected": true \| false }` based on whether `GROQ_API_KEY` is set in env |
| POST | `/api/config/groq-key` | Body: `{ "key": "gsk_..." }`. Writes literal key to `~/.config/chronicler/config.toml` under `[groq] api_key` and sets `os.environ["GROQ_API_KEY"]` |

### Required DB change — `get_all_recent_entries()`

`storage/db.py` requires a new method:

```python
def get_all_recent_entries(
    self,
    limit: int = 50,
    project_id: str | None = None,
    change_type: str | None = None,
    after_rowid: int | None = None,
) -> list[dict]:
    ...
```

Queries `log_entries` (using SQLite's implicit `rowid`, which is a monotonically increasing integer) joined with `projects`, ordered by `rowid DESC`. When `project_id` is `None`, returns entries across all projects. When `change_type` is `None`, no type filter is applied.

**Important:** The `id` column is a `TEXT` UUID — not suitable for ordering or cursor comparisons. Use SQLite's built-in `rowid` (always available, always monotonic) as the SSE cursor. The `after_rowid` parameter filters `WHERE rowid > after_rowid`.

The `/api/activity` route and the SSE stream both use this method. The existing `get_recent_entries(project_id, limit)` is untouched.

### Real-time flow

```
File saved → watcher → SQLite insert → SSE endpoint detects new row → pushes to browser → feed updates
```

The SSE endpoint polls `get_all_recent_entries(after_rowid=last_seen_rowid)` on a 1-second interval. On new rows, it pushes them as JSON events and updates `last_seen_rowid`. The browser appends entries to the top of the feed with a fade-in animation.

### Start/Stop daemon routes

`POST /api/projects/{id}/start` and `/api/projects/{id}/stop` operate as follows:

1. Look up the project by UUID `id` using `db.get_project_by_path()` (query by id) to get its `path`
2. **Start**:
   - Load config: `config = load_config(project_path)`
   - Load project: `project = db.get_project_by_path(str(project_path))`
   - Call `daemon.start_daemon(project_path, project, config, db)` (see refactor below)
3. **Stop**: call `daemon.stop_daemon(project_path)` (see refactor below)

**Refactor required** — extract daemon logic into `chronicler/core/daemon.py`:

```python
# chronicler/core/daemon.py

def start_daemon(project_path: Path, project, config, db) -> None:
    """Extracted from cli/main.py _daemonize(). Launches watcher as detached subprocess."""
    # ... same logic as current _daemonize() ...

def stop_daemon(project_path: Path) -> None:
    """Extracted from cli/main.py stop command. Reads PID file and sends SIGTERM."""
    import signal
    pid_file = project_path / ".chronicler" / "chronicler.pid"
    if not pid_file.exists():
        return
    pid = int(pid_file.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    pid_file.unlink(missing_ok=True)
```

`cli/main.py` `start` and `stop` commands are updated to call these helpers instead of inline logic. No behaviour change to the CLI.

Daemon status check (used by `GET /api/projects`): PID file exists AND `os.kill(pid, 0)` succeeds → `running`. Otherwise → `stopped`. Status is re-checked on every `/api/projects` call and polled every 5 seconds by the frontend.

**Note:** The "error" state (watcher crashed) is **out of scope for v1**. Detecting crash vs. clean stop requires a sentinel file protocol not present in the current daemon. The traffic light shows only green (running) or grey (stopped) in v1.

### `POST /api/projects/{id}/handoff` — implementation

```python
# Look up project by id, get its path
project = db.get_project_by_path(...)   # after resolving id → path
config = load_config(str(project_path))
map_mgr = MapManager(str(project_path / ".chronicler"))
sessions = 5  # default, same as CLI default

output = HandoffGenerator(config).generate(project, map_mgr.read(), db, sessions)

# Write to disk (same as CLI)
date_str = datetime.utcnow().strftime("%Y-%m-%d")
out_path = project_path / ".chronicler" / "handoffs" / f"{date_str}-handoff.md"
out_path.write_text(output)

return { "markdown": output, "saved_to": str(out_path) }
```

Import: `from chronicler.llm.classifier import HandoffGenerator`

### `POST /api/projects` — init logic

The route accepts a JSON body `{ "path": "/absolute/path/to/project", "name": "my-app" }`. It runs the following init steps server-side with these defaults (no interactive prompts):

1. Validate `path` exists and is a directory
2. Create `{path}/.chronicler/` and `{path}/.chronicler/handoffs/`
3. Write `{path}/.chronicler/config.toml` using the **exact sectioned format** that `load_config()` parses:
   ```toml
   [project]
   name = "my-app"
   framework = "nextjs"
   languages = []

   [logging]
   mode = "debounced"

   [models]
   tier = "cloud"
   ```
4. Call `MapManager(str(chronicler_dir)).create_initial(name, framework, [])` — `framework` is auto-detected via `_detect_framework(project_path)` from `cli/main.py` (extract to a shared location or import directly)
5. Register in DB via `db.insert_project(Project(id=str(uuid4()), name=name, path=str(path), created_at=datetime.utcnow(), git_enabled=(path/".git").exists(), primary_language="unknown", languages=[], framework=framework, description=None, log_mode="debounced", ignore_patterns=[], tags=[]))`
6. Append `.chronicler/\n` to `{path}/.gitignore` if it exists and `.chronicler/` isn't already present

Returns `{ "id": "...", "name": "...", "path": "...", "framework": "..." }` on success.

---

## Dashboard Layout

**Layout: Cards + Unified Feed (always-visible split)**

```
┌─────────────────────────────────────────────────────────┐
│  Chronicler v0.1.0                          ● Live       │  ← top bar
├──────────────────────┬──────────────────────────────────┤
│  PROJECTS        + Add│  Activity | Full Log    ✦ Handoff│
│                      │  [All][feature][bug fix]...       │
│  ● Macro    nextjs   │                                  │
│    14 changes · 3 ses│  M 03:27  feature  Added ttl_days│
│    [View map][Handoff]│  A 03:10  feature  Auth middlewar│
│                      │  M 03:17  refactor LLM selection │
│  ○ chronicler python │                                  │
│    0 changes today   │  ── Full Log tab ───────────────  │
│                      │  search + filters + session groups│
│  ● autark-web react  │                                  │
│    8 changes today   │                                  │
│                      │                                  │
│  + Add project       │                                  │
└──────────────────────┴──────────────────────────────────┘
```

### Left panel — Project cards

Each card shows:
- **Traffic light dot** (green = running, grey = stopped) — clickable to start/stop. Tooltip: "Watching for changes — click to stop" / "Not watching — click to start"
- Project name + detected framework badge
- Stats: changes today, session count, time active
- Action buttons: **View map** (opens `CHRONICLER_MAP.md` in a modal), **Handoff ✦** (generates handoff for this project)
- **+ Add project** button at the bottom of the list

### Right panel — Activity + Full Log tabs

**Activity tab (default):**
- Live SSE feed of recent entries across all watched projects
- Each entry shows: colour-coded project initial, change type badge, impact dot, relative time ("just now", "12 min ago"), file path, LLM summary
- Filter pills for change type. Display labels and their corresponding DB `change_type` values:

  | Pill label | DB value |
  |-----------|----------|
  | All | *(no filter)* |
  | feature | `feature` |
  | bug fix | `bug_fix` |
  | refactor | `refactor` |
  | config | `config` |
  | dependency | `dependency` |
  | style | `style` |
  | test | `test` |
  | docs | `docs` |
  | delete | `delete` |
  | experiment | `experiment` |

  All 10 change types appear as pills. The pill displays a human-readable label; the query uses the DB value.

- **✦ Generate Handoff** button (top right) — generates across all active projects

**Full Log tab:**
- Per-project dropdown filter at top (default: all projects)
- Free-text search against file path + summary
- Date range filter
- Change type filter (same pills as Activity tab)
- Entries grouped by session. Session header shows: date range, session health label (`productive` / `debugging` / `exploratory` / `maintenance`)
- Each entry shows: full timestamp (`2026-03-26 03:27:16`), change type badge, impact level, file path, summary
- Expandable diff: click entry to reveal the code diff inline

---

## Onboarding Flow

Shown on first launch (no projects in DB). A modal overlay with 4 steps and a progress bar.

### Step 1 — Welcome
Plain-English explanation: what Chronicler does, that it works silently in the background, no coding knowledge required. CTA: "Get started →"

### Step 2 — Add your first project
- **Path input**: plain text input where the user types or pastes the absolute path to their project folder. Tooltip on the input: "Paste the full path to your project folder — for example: /Users/yourname/projects/my-app". No file picker (browser security prevents reading filesystem paths from `<input type="file">`).
- Project name input (auto-filled from the last component of the path, editable)
- Auto-detects framework when the path is entered (debounced API call to `/api/detect-framework?path=...`), shows "✓ Next.js project detected" pill on success
- "I'll do this later" skip link

### Step 3 — Connect your AI key
- Explains Groq is free, no credit card needed, link to `console.groq.com`
- On load, calls `GET /api/config/groq-key-status` (add this route). The server checks `os.environ.get("GROQ_API_KEY")`. If set, returns `{ "detected": true }` — UI shows "✓ API key detected — you're all set" and auto-advances after 1 second.
- Otherwise: password input for key entry. On submit, the server calls `os.environ["GROQ_API_KEY"] = key` for the current process lifetime and writes `api_key = "<literal-key>"` under `[groq]` in `~/.config/chronicler/config.toml`. This matches how `load_config()` works: it reads `config.groq.api_key` as a plain string, then `settings.py` line 130 overlays `os.environ.get("GROQ_API_KEY")` on top — so writing the literal key to TOML is the correct path for persistence.
- Add `GET /api/config/groq-key-status` to the route table.
- "Skip — I'll add it later" link

### Step 4 — Done
- Checklist confirming what's set up
- Two hints: how to add more projects, how to generate a handoff
- "Open dashboard →" closes the modal

---

## Contextual Help

- **Tooltips** on all action buttons
- **Empty states**: "No changes logged yet — start coding and Chronicler will pick them up automatically"
- **Top bar hint**: rotates through 2–3 tips (e.g. "Click the coloured dot to start or stop watching a project")
- **Handoff button tooltip**: "Creates a briefing document so your AI coding assistant knows exactly where to pick up"

---

## Daemon Status Detection

Status is determined per-project on every `GET /api/projects` call:

```python
import os, signal

def get_daemon_status(project_path: str) -> str:
    pid_file = Path(project_path) / ".chronicler" / "chronicler.pid"
    if not pid_file.exists():
        return "stopped"
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)   # signal 0 = existence check, raises if dead
        return "running"
    except (ProcessLookupError, ValueError):
        pid_file.unlink(missing_ok=True)
        return "stopped"
```

Frontend polls `/api/projects` every 5 seconds to refresh traffic lights. SSE is reserved for activity entries only.

---

## Scope (v1)

**In scope:**
- `chronicler ui [--port] [--no-open]` CLI command (foreground, Ctrl-C to stop)
- FastAPI server + single HTML frontend (Alpine.js + Tailwind CDN)
- All API routes listed above (including `/api/detect-framework`, `/api/config/groq-key-status`, `/api/config/groq-key`)
- New `get_all_recent_entries(limit, project_id, change_type, after_rowid)` method in `db.py` using SQLite `rowid` as SSE cursor
- Daemon helpers extracted to `chronicler/core/daemon.py` (`start_daemon`, `stop_daemon`); CLI updated to call them
- Dashboard: project cards + activity feed + full log tab
- Onboarding flow (4 steps, path typed manually — no file picker)
- Contextual tooltips + empty states
- SSE live feed
- Generate handoff from UI (writes to `.chronicler/handoffs/` same as CLI)

**Out of scope (future):**
- macOS menubar/tray integration
- Error daemon state (requires sentinel file protocol change)
- Config editing from the UI
- Dark/light theme toggle
- Multi-user / remote access
- Browser folder picker (blocked by browser security sandbox)
