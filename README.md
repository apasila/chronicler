<p align="center">
  <img src="chronicler/ui/static/chron.png" alt="Chronicler" width="120">
</p>

# Chronicler

> **Every AI coding agent starts blind. Chronicler gives it memory.**

Chronicler is a background tool that silently watches your code projects while you work. Every time you save a file, it uses an AI model to understand *what* changed and *why* — then logs it to a searchable timeline. When you hand off to an AI coding agent (Claude, Cursor, Copilot, etc.), you generate a **Handoff** document in one click: a precise briefing that tells the agent exactly what was built, what's in progress, and what to tackle next.

**Free and open source. No account. No cloud sync. Your code never leaves your machine.**

---

## Table of Contents

- [What Does It Actually Do?](#what-does-it-actually-do)
- [Is This For Me?](#is-this-for-me)
- [Installation](#installation)
- [Getting a Free AI Key](#getting-a-free-ai-key)
- [Quick Start — 3 Steps](#quick-start--3-steps)
- [The Dashboard](#the-dashboard)
- [The Handoff — The Main Event](#the-handoff--the-main-event)
- [Model Options](#model-options)
- [Ignore Patterns — Filtering Out Noise](#ignore-patterns--filtering-out-noise)
- [How the AI Understands Your Changes](#how-the-ai-understands-your-changes)
- [Configuration](#configuration)
- [CLI Commands](#cli-commands)
- [Troubleshooting](#troubleshooting)
- [For Developers](#for-developers)
- [Privacy](#privacy)
- [License](#license)

---

## What Does It Actually Do?

Imagine you've been coding for 4 hours. You added a login system, fixed a bug in the payment flow, and started building a new dashboard. Now you want Claude or Cursor to continue your work — but the agent has no idea any of this happened.

Without Chronicler, you either:
- Spend 10–20 minutes writing a context document manually
- Paste random code snippets and hope the agent figures it out
- Start a session with "here's what I'm working on..." and inevitably forget something important

With Chronicler running in the background, you click **✦ Generate Handoff** and get this in seconds:

```
## What Was Built Today
- Built JWT authentication with 15-minute access tokens and 7-day refresh tokens
- Added POST /api/auth/login with bcrypt password verification
- Fixed token expiry bug (was comparing local time vs UTC — caught by a failing test)
- Added voice service with ASR and TTS, wired to Telegram bot

## Work In Progress
- Token refresh endpoint started but not yet tested
- Executive briefing email filtering has edge cases with newsletters

## Suggested Next Steps
1. Complete the POST /api/auth/refresh endpoint with token rotation
2. Add rate limiting to /api/auth/login (currently unprotected)
3. Write integration tests for the full auth flow

## Key Files Changed Today
- apps/server/src/services/auth.ts (core logic)
- apps/server/src/routes/admin.ts (4 changes — most active file)
- apps/server/src/services/voice.ts (new file)
```

Paste that at the top of your next AI session. The agent instantly knows your entire codebase context.

---

## Is This For Me?

**Yes, if you:**
- Use AI coding agents (Claude, Cursor, GitHub Copilot, Windsurf, etc.) regularly
- Switch between AI sessions and lose context each time
- Work on projects that span multiple days or sessions
- Want a searchable log of what you (or an AI agent) actually built
- Are concerned about AI agents "going blind" partway through a task

**You don't need to be a developer to use the dashboard.** If you can run a terminal command to install it, everything else is point-and-click.

---

## Installation

### What You Need First

- **Python 3.11 or newer** — [download here](https://www.python.org/downloads/) if you don't have it
- A terminal (Terminal on Mac, Command Prompt or PowerShell on Windows)
- One of: a free Groq API key (easiest), a local Ollama install, or another AI server

**Check your Python version:**
```bash
python3 --version
```
It should say `Python 3.11.x` or higher.

### Install Chronicler

```bash
pip install git+https://github.com/your-username/chronicler.git
```

That's it. Chronicler is now a command available in your terminal.

**Verify it installed:**
```bash
chronicler --help
```
You should see a list of commands.

---

## Getting a Free AI Key

Chronicler needs an AI model to understand your code changes. The easiest option is **Groq** — it's free, fast, and doesn't require a credit card.

1. Go to [console.groq.com/keys](https://console.groq.com/keys)
2. Sign up (free) and create an API key
3. Copy the key — it starts with `gsk_`

You'll paste this into the Chronicler dashboard in the next step. You can also set it as an environment variable if you prefer:

```bash
# Mac / Linux — add this line to ~/.zshrc or ~/.bashrc
export GROQ_API_KEY="gsk_your_key_here"
```

**Alternative: use a local model** — see [Model Options](#model-options) if you want everything to stay on your machine with no external API calls.

---

## Quick Start — 3 Steps

### Step 1: Launch the dashboard

```bash
chronicler ui
```

Your browser opens at `http://localhost:8765`. You'll see the Chronicler dashboard.

### Step 2: Add your API key

Click the **gear icon ⚙** in the top-right corner. Paste your Groq API key and click **Save**.

### Step 3: Add your first project

Click **+ Add project** in the sidebar. Use **Choose folder** to pick the folder where your code lives. Chronicler will auto-detect your framework and start watching immediately.

The green dot in the sidebar means Chronicler is actively watching that project. **You're done.** Just code normally — Chronicler runs silently in the background.

---

## The Dashboard

### Sidebar — Your Projects

Each project card in the left sidebar shows:

| Element | What it means |
|---------|---------------|
| **Green dot** | Watching — click to pause |
| **Yellow dot** | Paused — click to resume |
| **"832 changes today"** | Total logged changes today |
| **Map** button | View an auto-generated overview of the project |
| **✦ Handoff** button | Generate a briefing for an AI agent |
| **×** button | Remove the project from Chronicler |

**The dot is your on/off switch.** Click it once to pause watching, click again to resume.

### Activity Tab

The main feed shows every logged change, most recent at the top. Each entry shows:

- **Who** changed it (the project initial — "M" for Macro, etc.)
- **What type** of change it was (colour-coded pill):
  - `feature` — new functionality
  - `bug fix` — fixing something broken
  - `refactor` — restructuring code without changing behaviour
  - `config` — configuration files, build setup
  - `dependency` — packages added, removed, or updated
  - `style` — formatting, naming, comments
  - `test` — test files
  - `docs` — documentation
  - `delete` — code or files removed
  - `experiment` — exploratory work, likely to change
- **Impact level** (dot colour): red = high, amber = medium, green = low
- **File path** — which file changed
- **Summary** — a one-sentence AI-generated description of what changed

Click any entry to expand and see the actual code diff.

**Filter chips** at the top let you show only certain change types — click `feature` to see only features, `bug fix` to see only fixes, etc.

### Full Log Tab

All changes grouped by **session**. A session is a continuous block of coding activity. A new session starts automatically after 30 minutes of inactivity. This view is useful for reviewing what happened in a specific work block.

### The Live Indicator

The green **Live** badge in the top-right corner means the dashboard is receiving real-time updates. Changes appear within seconds of you saving a file — no manual refresh needed.

---

## The Handoff — The Main Event

This is the feature that makes Chronicler genuinely useful for AI-assisted development.

### How to Generate One

1. Click **✦ Handoff** on any project card in the sidebar, or click **✦ Generate Handoff** in the toolbar (generates for the most recently active project)
2. Wait a few seconds while the AI reads your session history
3. A formatted briefing document appears in a modal — read it, copy it, or use it directly

The handoff document is also saved automatically to `.chronicler/handoffs/YYYY-MM-DD-handoff.md` inside your project folder.

### What Goes Into a Handoff

The AI reads your recent change history across sessions and synthesises:

- **Project overview** — what the project is and its current state
- **What was built recently** — a concise list of completed work
- **Work in progress** — things that were started but not finished
- **Open threads and known issues** — bugs spotted, edge cases noted
- **Key decisions made** — architectural choices visible in the diff history
- **Most active files** — what's changing most, indicating current focus areas
- **Suggested next steps** — logical continuation based on the work patterns

### How to Use It With an AI Agent

Simply paste the handoff document at the start of your AI session:

```
Here's the current state of my project:

[paste handoff here]

Please continue the work. Start with [specific task].
```

The agent now has full context — what's done, what's in progress, what to avoid, and what to do next.

### Handoff Quality Tips

- **Generate after a productive session**, not in the middle of one
- **The more real changes logged, the better** — make sure your ignore patterns filter out build artifacts (see below)
- **Sessions matter** — the AI uses session boundaries to understand work blocks; the 30-minute gap is configurable

---

## Model Options

Open **Settings ⚙** in the top-right corner to switch between providers.

### Groq (Recommended — Free)

The default. Fast inference, generous free tier, no credit card required.

- Get your key: [console.groq.com/keys](https://console.groq.com/keys)
- Available models in the dropdown:
  - `llama-3.3-70b-versatile` — best quality (default)
  - `llama-3.1-8b-instant` — faster, lighter, slightly less accurate
  - `mixtral-8x7b-32768` — good for long context
  - `gemma2-9b-it` — Google's model, efficient

### Ollama (Local — Private)

Run models on your own machine. Nothing leaves your computer.

1. Install Ollama: [ollama.com](https://ollama.com)
2. Pull a model: `ollama pull llama3.2` (or any model you prefer)
3. Start it: `ollama serve`
4. In Chronicler Settings, switch to **Ollama**, set the model name, and save

Good model choices for code understanding: `llama3.2`, `codellama`, `phi4`, `deepseek-coder`

### Custom (OpenAI-Compatible Server)

Works with **llama.cpp**, **LM Studio**, **vLLM**, **Jan**, and any server that speaks the OpenAI API format.

1. Start your local server (it will give you a URL like `http://localhost:8080/v1`)
2. In Settings, switch to **Custom**, enter the URL, your model name, and optionally an API key
3. Save

### After Changing Models

Click **Save**, then **restart the project watchers** (click the dot to pause, then click again to resume). The watchers load the model config on startup.

---

## Ignore Patterns — Filtering Out Noise

This is important. Without proper ignore patterns, Chronicler will log thousands of meaningless build artifact changes and the handoff quality will suffer.

### Opening the Ignore Editor

Click **Settings ⚙** and scroll to the **Ignore Patterns** section at the bottom. Patterns are shown as removable chips. Type a pattern in the input and press Enter or click **+ Add**.

### What to Ignore

**Always ignore** (these are already in the defaults):
```
node_modules/**     ← JavaScript dependencies
.git/**             ← Git internals
*.lock              ← Lock files (package-lock.json, yarn.lock, etc.)
*.log               ← Log files
dist/**             ← Build output
build/**            ← Build output
.env                ← Environment variables (sensitive!)
__pycache__/**      ← Python compiled files
*.pyc               ← Python bytecode
.DS_Store           ← Mac desktop services file
```

**Add these if you use them:**
```
.next/**            ← Next.js build cache (generates hundreds of changes per build)
*.tsbuildinfo       ← TypeScript build info
.nuxt/**            ← Nuxt.js build cache
.vite/**            ← Vite cache
coverage/**         ← Test coverage reports
*.min.js            ← Minified files
*.min.css           ← Minified stylesheets
uploads/**          ← Uploaded files / data files
*.json              ← If you have lots of auto-generated JSON
workspace/memory/** ← AI agent memory files
```

### Pattern Syntax

Patterns follow standard glob syntax:

| Pattern | Matches |
|---------|---------|
| `*.log` | Any file ending in `.log` |
| `dist/**` | Everything inside the `dist` folder |
| `.next/**` | Everything inside `.next` |
| `**/*.min.js` | Minified JS files anywhere |
| `.env*` | `.env`, `.env.local`, `.env.production`, etc. |

### A Note on Signal Quality

Chronicler's value scales directly with signal quality. If your log is full of build artifacts, the AI has to wade through noise to find the real work. With good ignore patterns, every entry in your activity feed represents something a human actually wrote — and the handoff becomes genuinely insightful.

---

## How the AI Understands Your Changes

Every time a watched file is saved, here's what happens:

```
1. File save detected by the file watcher
2. Debouncer waits 10 seconds for burst saves to settle
   (so saving 20 files quickly counts as one event, not 20)
3. Git diff generated (or a raw diff if no git repo)
4. Diff sent to your AI model with a classification prompt
5. Model returns: change type, impact level, one-line summary
6. Entry saved to local SQLite database
7. Appears live in the dashboard activity feed
```

The AI is given context about recent changes to the same file, your project name, and detected framework — so summaries get smarter over time as it builds up context.

### Change Classification Prompt

The AI is asked to classify each change as one of the [10 change types](#activity-tab) with an impact level and a plain-English summary. It's prompted to be concise and factual — not to editorialize or speculate.

### The Debounce Window

The default 10-second debounce means if you save rapidly (e.g. auto-save fires 5 times in 3 seconds), Chronicler processes it once, not 5 times. You can adjust this in `~/.config/chronicler/config.toml`:

```toml
[logging]
debounce_seconds = 10    # increase if you have aggressive auto-save
```

---

## Configuration

### Global Config File

Located at `~/.config/chronicler/config.toml` — applies to all projects.

```toml
[logging]
default_mode = "debounced"     # "every_save" | "debounced" | "session_only"
session_gap_minutes = 30       # minutes of inactivity before a new session starts
debounce_seconds = 10          # seconds to wait after last save before processing

[models]
workhorse = "groq/llama-3.3-70b-versatile"   # model used for every change
premium   = "groq/llama-3.3-70b-versatile"   # model used for handoff generation

[groq]
api_key = ""                   # set via Settings UI or GROQ_API_KEY env var

[ollama]
enabled = false
base_url = "http://localhost:11434"
workhorse_model = "phi4"

[custom]
enabled = false
base_url = "http://localhost:8080/v1"
api_key = ""
model = "local-model"

[ignore]
global_patterns = [
  "node_modules/**", ".git/**", "*.lock", "*.log",
  "dist/**", "build/**", ".env", ".env.*",
  "__pycache__/**", ".DS_Store", "*.pyc",
  ".next/**", "*.tsbuildinfo"
]

[storage]
db_path = "~/.config/chronicler/chronicler.db"
max_db_size_mb = 500
```

### Per-Project Config

Each watched project gets a `.chronicler/config.toml` that overrides global settings for just that project:

```toml
[project]
name = "my-app"
framework = "nextjs"

[logging]
mode = "every_save"          # override: log every save without debouncing

[ignore]
patterns = ["src/generated/**", "*.test.ts"]
```

### Config Priority

```
~/.config/chronicler/config.toml   ← global defaults
         overridden by ↓
.chronicler/config.toml            ← per-project settings
         overridden by ↓
GROQ_API_KEY environment variable  ← always wins for the API key
```

### Log Modes

| Mode | Behaviour | Best for |
|------|-----------|---------- |
| `debounced` | Waits 10s of quiet before processing (default) | Most projects |
| `every_save` | Processes each save individually | When you want maximum granularity |
| `session_only` | Only logs session summaries, not individual changes | Noisy projects |

---

## CLI Commands

The web dashboard covers everything for most users. The CLI is available if you prefer working in the terminal or want to automate things.

```bash
# Launch the web dashboard
chronicler ui
chronicler ui --port 8888          # use a different port
chronicler ui --no-open            # don't auto-open browser

# Project setup (interactive wizard)
chronicler init
chronicler init --path /path/to/project --name "My App"

# Start/stop watching
chronicler start                   # start as background daemon
chronicler start --foreground      # run in terminal with live output (Ctrl+C to stop)
chronicler stop                    # stop the daemon
chronicler status                  # show status and recent entries

# Browse the change log
chronicler log                     # last 20 entries
chronicler log --limit 100
chronicler log --change-type feature
chronicler log --change-type bug_fix

# Generate a handoff briefing
chronicler handoff                 # uses last 5 sessions
chronicler handoff --sessions 10   # use last 10 sessions

# View the project map
chronicler map
```

### Running in Foreground Mode

Useful for seeing exactly what Chronicler is doing:

```bash
chronicler start --foreground
```

Output looks like:
```
Watching /Users/you/my-project... (Ctrl+C to stop)

14:23:01 src/auth.ts → feature: Added JWT token refresh endpoint
14:23:45 src/auth.ts → bug_fix: Fixed token expiry comparison using UTC
14:31:12 package.json → dependency: Added jsonwebtoken 9.0.0
```

---

## Troubleshooting

### "0 changes today" even though the watcher is running

**Most likely cause: invalid or missing API key.**

1. Open Settings ⚙ in the dashboard
2. Re-enter your Groq API key and click Save
3. Stop and restart the project watcher (click the green dot twice)
4. Make a small change in your project and save

To see exactly what's happening, check the daemon log:
```bash
cat your-project/.chronicler/daemon.log
```
This shows any errors the watcher is encountering.

**Second most likely cause: noisy ignore patterns are blocking everything.**
Check your ignore patterns in Settings — if you have `**` or `*` as a pattern, it will block all files.

### The "Choose folder" button does nothing

Hard-refresh the dashboard: **Cmd+Shift+R** (Mac) or **Ctrl+Shift+R** (Windows/Linux). This is usually a browser cache issue.

### The dashboard shows an old version after updating

Always hard-refresh after restarting the server: **Cmd+Shift+R** (Mac) or **Ctrl+Shift+R** (Windows/Linux).

### Ctrl+C doesn't stop the server

This was a known bug in early versions — the SSE live-update connection would prevent clean shutdown. It is fixed in v0.1.0+.

### Port 8765 is already in use

```bash
chronicler ui --port 8766
```

### The watcher logs `.next/**` build files as changes

Add `.next/**` to your ignore patterns in Settings. Next.js regenerates these files on every build. Same applies to `dist/**`, `build/**`, `*.tsbuildinfo` for other frameworks.

### Changes appear but the handoff seems generic

The handoff quality improves with more clean signal. Make sure:
1. Your ignore patterns are filtering out build artifacts
2. You've made a reasonable number of real source changes (at least 5–10)
3. Try generating after a focused work session rather than at the start of the day

### "Process exited immediately" when starting a watcher

Check the daemon log for the error:
```bash
cat your-project/.chronicler/daemon.log
```
Common causes: the project path no longer exists, or `chronicler` isn't found in `PATH`.

### Checking if Chronicler is running

```bash
# Check the process
ps aux | grep "chronicler start"

# Check the PID file
cat your-project/.chronicler/chronicler.pid
```

---

## For Developers

### Project Structure

```
chronicler/
├── core/
│   ├── watcher.py        # watchdog setup, file event routing
│   ├── debouncer.py      # burst-save coalescing (thread-safe)
│   ├── differ.py         # git diff or raw unified diff + language detection
│   ├── daemon.py         # background process management (start/stop/pid/log)
│   └── context.py        # session lifecycle, recent entry context
├── llm/
│   ├── client.py         # litellm wrapper — routes to Groq, Ollama, or custom
│   ├── prompts.py        # all prompt templates (versioned)
│   └── classifier.py     # EntryClassifier, SessionSummarizer, MapUpdater,
│                         #   HandoffGenerator
├── storage/
│   ├── db.py             # SQLite CRUD (thread-safe, WAL mode)
│   ├── schema.py         # Pydantic v2 models + controlled vocabularies
│   └── map.py            # CHRONICLER_MAP.md read/write/update
├── ui/
│   ├── server.py         # FastAPI server + all REST API endpoints
│   └── static/
│       └── index.html    # single-file dashboard (Alpine.js + Tailwind CDN)
├── cli/
│   └── main.py           # typer CLI — all commands
└── config/
    └── settings.py       # 3-tier TOML config loader with env var override
```

### Tech Stack

| Layer | Technology |
|-------|------------|
| File watching | [watchdog](https://github.com/gorakhargosh/watchdog) |
| LLM integration | [litellm](https://github.com/BerriAI/litellm) (supports 100+ providers) |
| Database | SQLite (via stdlib `sqlite3`, WAL mode) |
| Data models | [Pydantic v2](https://docs.pydantic.dev) |
| Web server | [FastAPI](https://fastapi.tiangolo.com) + [uvicorn](https://www.uvicorn.org) |
| CLI | [Typer](https://typer.tiangolo.com) + [Rich](https://rich.readthedocs.io) |
| Dashboard UI | [Alpine.js](https://alpinejs.dev) + [Tailwind CSS](https://tailwindcss.com) (CDN) |

### Running From Source

```bash
git clone https://github.com/your-username/chronicler.git
cd chronicler
pip install -e ".[dev]"
pytest
chronicler ui
```

### API Endpoints

The dashboard talks to a local FastAPI server. All endpoints are available at `http://localhost:8765`:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/projects` | List all projects with status |
| `POST` | `/api/projects` | Add a new project |
| `DELETE` | `/api/projects/{id}` | Remove a project |
| `POST` | `/api/projects/{id}/start` | Start the file watcher |
| `POST` | `/api/projects/{id}/stop` | Stop the file watcher |
| `GET` | `/api/projects/{id}/map` | Get the project map markdown |
| `POST` | `/api/projects/{id}/handoff` | Generate a handoff document |
| `GET` | `/api/activity` | Get recent log entries |
| `GET` | `/api/activity/stream` | SSE stream for live updates |
| `GET` | `/api/browse` | Browse filesystem directories |
| `GET` | `/api/config/provider` | Get current model/ignore config |
| `POST` | `/api/config/provider` | Save model/ignore config |

### Database Schema

All data lives in `~/.config/chronicler/chronicler.db`. The main tables:

- **`projects`** — registered projects (id, name, path, framework, log_mode)
- **`sessions`** — work sessions (id, project_id, start/end timestamps, summary)
- **`log_entries`** — individual change events (file info, change type/impact/summary, diff snapshot, LLM metadata)

### Adding a New LLM Provider

Chronicler uses [litellm](https://docs.litellm.ai/docs/providers) under the hood, which supports 100+ providers. To add a new one:

1. Set the `workhorse` model string in config to the litellm format for your provider
2. Set any required API key environment variables litellm expects
3. If the provider needs a custom `api_base`, use the **Custom** provider option in Settings

### Security Note — litellm

In March 2026, litellm versions **1.82.7** and **1.82.8** were compromised in a supply chain attack (credential stealer). Chronicler requires `litellm>=1.30` — ensure you are on **1.82.6 or earlier**, or **1.82.9 or later** once a clean version is published. Check your version:

```bash
pip show litellm
```

---

## Project Files

Chronicler creates a `.chronicler/` folder inside each watched project:

```
your-project/
└── .chronicler/
    ├── config.toml          ← project-level config overrides
    ├── chronicler.pid        ← daemon process ID (managed automatically)
    ├── daemon.log            ← daemon output and error log (check this for issues)
    ├── CHRONICLER_MAP.md     ← auto-maintained project overview
    └── handoffs/
        ├── 2026-03-28-handoff.md
        └── 2026-03-30-handoff.md
```

`.chronicler/` is automatically added to `.gitignore` when you add a project.

All change logs are stored in `~/.config/chronicler/chronicler.db` — a single SQLite database shared across all your projects. You can query it directly with any SQLite browser.

---

## Privacy

- **No telemetry.** Nothing is ever sent to Chronicler servers because there are no Chronicler servers.
- **Your code diffs are sent to your chosen AI provider** (Groq, or whoever you configure) for inference only. They are not stored beyond the inference call. Use Ollama or a local server if you want zero external calls.
- **API keys** are stored in `~/.config/chronicler/config.toml` on your machine. They are never transmitted anywhere except to your AI provider for authentication.
- **The change log** lives entirely in `~/.config/chronicler/chronicler.db` on your machine.
- **`.chronicler/`** is gitignored by default — handoff documents and logs do not end up in your repository.

---

## License

MIT — free to use, modify, and distribute.

---

## Contributing

Issues and pull requests welcome. The codebase is intentionally simple — the entire dashboard UI is a single HTML file, the backend is a single FastAPI file, and the core pipeline is four small Python modules.

If you find a bug, check `.chronicler/daemon.log` first — it usually tells you exactly what went wrong.
