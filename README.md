# Chronicler

A background daemon that watches your project folders and automatically logs every meaningful code change using an LLM. Creates a rich, structured timeline of development activity — and generates context-rich handoff packets so AI coding agents can pick up exactly where you left off.

**Every coding agent starts blind. Chronicler gives it memory.**

---

## How It Works

```
File Save
  → watchdog detects change
  → debouncer waits for burst saves to settle
  → differ generates a unified diff
  → LLM classifies the change (type, impact, summary)
  → entry written to SQLite
  → CHRONICLER_MAP.md updated if needed
  → session tracked automatically
```

When you need to hand off to an AI agent, run `chronicler handoff` — it reads your entire session history and produces a precise briefing document the agent can act on immediately.

---

## Installation

**Requirements:** Python 3.11+, a [Groq](https://console.groq.com) API key (free tier works fine)

```bash
pip install git+https://github.com/apasilacyans/chronicler.git
```

Set your API key:

```bash
export GROQ_API_KEY="your-key-here"
# Add to ~/.zshrc or ~/.bashrc to persist
```

---

## Quick Start

```bash
cd your-project
chronicler init
chronicler start --foreground
```

That's it. Chronicler is now watching your files. Every time you save, it quietly classifies the change and logs it.

---

## CLI Commands

### `chronicler init`

Sets up a project for watching. Auto-detects your framework and git status. Creates `.chronicler/config.toml` and registers the project in the global database.

```
$ chronicler init

Chronicler — Project Setup
──────────────────────────
Project name [my-app]:
Git repository detected ✓
Framework detected: nextjs ✓

Log mode:
  1. debounced (recommended)
  2. every_save
  3. session_only
Choice [1]:

Model tier:
  1. cloud via Groq (requires GROQ_API_KEY)
  2. local via Ollama
Choice [1]:

GROQ_API_KEY found in environment ✓
──────────────────────────
✓ .chronicler/config.toml created
✓ Project registered in chronicler.db
✓ Run `chronicler start` to begin watching
```

### `chronicler start`

Starts the file watcher daemon.

```bash
chronicler start              # background (detached)
chronicler start --foreground # run in terminal, Ctrl+C to stop
```

In foreground mode you'll see live output as changes are logged:

```
14:23:01 src/auth.ts → feature: Added JWT token refresh endpoint
14:23:45 src/auth.ts → bug_fix: Fixed token expiry comparison using UTC
14:31:12 package.json → dependency: Added jsonwebtoken 9.0.0
```

### `chronicler stop`

```bash
chronicler stop
```

### `chronicler status`

Shows daemon status and the 5 most recent log entries for the current project.

```
╭─────────────────╮
│ my-app          │
╰─────────────────╯
Daemon: running
Mode: debounced

         Recent Activity
┌──────────┬──────────────┬──────────┬──────────────────────────────────────┐
│ Time     │ File         │ Type     │ Summary                              │
├──────────┼──────────────┼──────────┼──────────────────────────────────────┤
│ 14:31:12 │ package.json │ dependency│ Added jsonwebtoken 9.0.0            │
│ 14:23:45 │ src/auth.ts  │ bug_fix  │ Fixed token expiry comparison        │
│ 14:23:01 │ src/auth.ts  │ feature  │ Added JWT token refresh endpoint     │
└──────────┴──────────────┴──────────┴──────────────────────────────────────┘
```

### `chronicler log`

Browse the full change log with filtering.

```bash
chronicler log                        # last 20 entries
chronicler log --limit 50             # last 50
chronicler log --change-type bug_fix  # only bug fixes
```

### `chronicler handoff`

Generates a handoff briefing for an AI coding agent. Uses the premium model (120B) for best quality. Reads your session history, open threads, and key decisions.

```bash
chronicler handoff             # uses last 5 sessions
chronicler handoff --sessions 10
```

Output is printed to the terminal **and** saved to `.chronicler/handoffs/YYYY-MM-DD-handoff.md`.

Example output:

```markdown
## Project Overview
Next.js SaaS app with Python backend. Currently implementing JWT authentication
with refresh token rotation. Core auth flow is 80% complete.

## What Was Built Recently
- Built POST /api/auth/login endpoint with bcrypt password verification
- Added JWT generation with 15-minute access + 7-day refresh tokens
- Fixed token expiry bug (was comparing local time vs UTC)
- Added jsonwebtoken 9.0.0 dependency

## Open Threads & Known Issues
- Token refresh endpoint not yet implemented
- Mobile Safari fails to persist refresh token in httpOnly cookie
- Rate limiting not yet added to login endpoint

## Suggested Next Steps
1. Implement POST /api/auth/refresh using the refresh token rotation pattern
2. Add rate limiting middleware to /api/auth/login
3. Write integration tests for the full auth flow
...
```

### `chronicler map`

View the auto-maintained project map.

```bash
chronicler map
```

The map is a markdown file (`.chronicler/CHRONICLER_MAP.md`) that Chronicler keeps up to date as your project evolves. It tracks features, routes, dependencies, and recent sessions.

---

## Change Types

The LLM classifies every change into exactly one of these types:

| Type | When |
|------|------|
| `feature` | New functionality added |
| `bug_fix` | Fixing broken behaviour |
| `refactor` | Restructuring without behaviour change |
| `style` | Formatting, naming, comments only |
| `config` | Config files, env, build setup |
| `dependency` | Package additions / updates / removals |
| `test` | Test files only |
| `docs` | Documentation only |
| `delete` | File or significant code removed |
| `experiment` | Exploratory, likely to be reverted |

Impact levels: `low` (cosmetic) · `medium` (functional, limited scope) · `high` (affects multiple systems)

---

## Configuration

### Global Config — `~/.config/chronicler/config.toml`

Created automatically on first `chronicler init`. Controls defaults for all projects.

```toml
[logging]
default_mode = "debounced"    # every_save | debounced | session_only
session_gap_minutes = 30      # idle gap before a new session starts
debounce_seconds = 10         # wait this long after last save before processing

[models]
tier = "cloud"                # cloud | local
workhorse = "groq/llama-3.3-70b-versatile"   # runs on every save
premium = "groq/llama-3.3-70b-versatile"     # used for handoff generation only

[groq]
api_key = "env:GROQ_API_KEY"  # always via env — never stored in plain text

[ignore]
global_patterns = [
  "node_modules/**", ".git/**", "*.lock",
  "dist/**", "build/**", ".env", "__pycache__/**"
]
```

### Project Config — `.chronicler/config.toml`

Optional. Overrides global defaults for one project.

```toml
[project]
name = "my-app"
framework = "nextjs"

[logging]
mode = "every_save"           # override: log every save, not debounced

[models]
tier = "local"                # use Ollama for this project

[ignore]
patterns = ["src/generated/**", "*.test.ts"]
```

### Config Cascade

```
~/.config/chronicler/config.toml   (global defaults)
       ↓ overridden by
.chronicler/config.toml            (project overrides)
       ↓ overridden by
GROQ_API_KEY env var               (always wins)
```

### Using Ollama (local models)

```toml
# ~/.config/chronicler/config.toml
[models]
tier = "local"

[ollama]
enabled = true
base_url = "http://localhost:11434"
workhorse_model = "phi4"
premium_model = "phi4"
```

---

## Project Files

Chronicler creates a `.chronicler/` folder in your project:

```
.chronicler/
├── config.toml          # project-level config overrides
├── CHRONICLER_MAP.md    # auto-maintained project map
└── handoffs/
    └── 2025-03-24-handoff.md
```

`.chronicler/` is automatically added to your `.gitignore` on init.

All logs are stored in `~/.config/chronicler/chronicler.db` — a single SQLite database shared across all your projects.

---

## Sessions

Chronicler groups your work into sessions automatically. A new session starts when there's been no activity for `session_gap_minutes` (default: 30 minutes).

At the end of a session, Chronicler runs a summary prompt that produces:
- What was accomplished (2-3 sentences)
- Key decisions made
- Open threads (things started but unfinished)
- Session health (`productive` / `exploratory` / `debugging` / `maintenance`)

Session summaries feed into the handoff generator, giving it temporal context.

---

## Privacy

- **No telemetry** unless you set `telemetry = true` in config
- **API keys never written to disk** in plain text — always via env ref
- **Diffs are sent to Groq for inference only** — logs never leave your machine
- **No account required** for any feature
- `.chronicler/` folder is gitignored by default

---

## Architecture

```
chronicler/
├── core/
│   ├── watcher.py      # watchdog setup, file event routing
│   ├── debouncer.py    # burst-save coalescing (thread-safe)
│   ├── differ.py       # git diff or raw unified diff + language detection
│   └── context.py      # recent entry fetching, session lifecycle
├── llm/
│   ├── client.py       # litellm wrapper, model routing by task
│   ├── prompts.py      # all prompt templates + version tracking
│   └── classifier.py   # EntryClassifier, SessionSummarizer, MapUpdater, HandoffGenerator
├── storage/
│   ├── db.py           # SQLite CRUD (thread-safe)
│   ├── schema.py       # Pydantic models + controlled vocabularies
│   └── map.py          # CHRONICLER_MAP.md read/write/update
├── cli/
│   └── main.py         # typer CLI — all 7 commands
└── config/
    └── settings.py     # 3-tier TOML config loader
```

**Tech stack:** Python 3.11+ · [watchdog](https://github.com/gorakhargosh/watchdog) · [litellm](https://github.com/BerriAI/litellm) · SQLite · [Pydantic v2](https://docs.pydantic.dev) · [Typer](https://typer.tiangolo.com) · [Rich](https://rich.readthedocs.io)

---

## Development

```bash
git clone https://github.com/apasilacyans/chronicler.git
cd chronicler
pip install -e ".[dev]"
pytest
```

---

## License

MIT
