# Tech Stack Sheet — Design Spec
**Date:** 2026-04-04
**Status:** Approved

## Overview

Each Chronicler-watched project gets a canonical tech stack sheet: a machine-readable source of truth (`.chronicler/tech-stack.json`) and a human/agent-readable summary (`STACK.md` in the project root). The goal is to prevent agent drift — when Cursor, Claude, or any coding agent opens a project cold, they immediately know the established tech decisions and won't introduce conflicting libraries, frameworks, or patterns.

---

## Data Model

The source of truth is `.chronicler/tech-stack.json`. Every detected item is a `StackEntry`:

```json
{
  "key": "react",
  "category": "library",
  "value": "18.2.0",
  "source": "package.json",
  "confidence": 1.0,
  "detected_at": "2026-04-04T10:00:00Z",
  "last_verified": "2026-04-04T10:00:00Z",
  "reason": null
}
```

LLM-inferred entries include a `reason` field:

```json
{
  "key": "lucide-react",
  "category": "icons",
  "value": "active",
  "source": "llm_inference",
  "confidence": 0.9,
  "detected_at": "2026-04-04T10:00:00Z",
  "last_verified": "2026-04-04T10:00:00Z",
  "reason": "found in 14 imports across 8 component files"
}
```

**Categories:** `language`, `runtime`, `framework`, `library`, `service`, `font`, `color`, `icons`, `tooling`, `devops`

**Top-level JSON structure:**

```json
{
  "generated_at": "2026-04-04T10:00:00Z",
  "manifest_hash": "abc123...",
  "entries": [...],
  "constraints": [
    "Do not introduce a second state management library — Zustand is the only one",
    "All colors must come from the palette defined below"
  ]
}
```

The `constraints` array is manually authored by the developer and survives regeneration — on every regeneration, Chronicler reads the existing JSON first, preserves `constraints`, then overwrites everything else. The `manifest_hash` is a SHA-256 of the concatenated content of all detected manifest files, used for staleness detection.

---

## Detection Pipeline

Lives in a new `chronicler/stack/` module with three components.

### Stage 1 — Static Extractor (`stack/extractor.py`)

Deterministic parsers, no LLM, confidence always `1.0`. Runs fast and free.

| File | What it extracts |
|---|---|
| `package.json` | libraries + versions, Node runtime |
| `pyproject.toml` / `requirements.txt` | Python libs + versions |
| `Cargo.toml` | Rust crates + versions |
| `go.mod` | Go modules |
| `tsconfig.json` | TypeScript target, strict mode |
| `tailwind.config.*` | colors, fonts |
| `*.css` / `*.scss` | CSS custom properties (colors, font-family) |
| `.env.example` | 3rd party services inferred from key names (e.g. `STRIPE_API_KEY` → Stripe) |

### Stage 2 — LLM Enricher (`stack/enricher.py`)

Receives Stage 1 results + a sample of up to 20 source files (prioritized by number of import statements referencing installed packages — files doing the most importing are most informative). Asks the LLM to:

- Identify which installed libs are actively used vs just present
- Detect icon packages and fonts not captured by static analysis
- Infer architectural decisions worth preserving as constraints
- Flag anything Stage 1 missed

Outputs entries with `source: "llm_inference"`, lower confidence scores, and `reason` populated.

### Renderer (`stack/renderer.py`)

Converts `.chronicler/tech-stack.json` → `STACK.md` in the project root.

`STACK.md` structure:
1. **Staleness warning** (only shown when stale — omitted on clean sheet)
2. **Inventory table** — auto-maintained, grouped by category, regenerated each time
3. **Decisions & Constraints** — pulled from `constraints[]` array verbatim; human-authored, not auto-generated

Example `STACK.md`:

```markdown
# Tech Stack

> Last verified: 2026-04-04

## Languages & Runtime
| Key | Value | Confidence |
|-----|-------|------------|
| TypeScript | 5.4 | ✓ |
| Node.js | 20 | ✓ |

## Libraries
...

## Services
...

## Design
...

## Decisions & Constraints
- Do not introduce a second state management library — Zustand is the only one
- All colors must come from the palette defined above
```

---

## Trigger Logic

### Auto-trigger

Hooked into the existing watcher. When a file matching manifest patterns fires a change event, the stack pipeline is called instead of (or in addition to) the normal change-log pipeline. The existing `MAP_TRIGGER_PATTERNS` is extended to ensure all manifest files are covered. Branch logic in `daemon.py`:

```
file change → watcher → is manifest file? → yes → stack pipeline (+ normal log entry with type=dependency)
                                           → no  → normal change log pipeline
```

Normal debouncing applies — no separate debouncer needed.

### Manual trigger

New endpoint: `POST /api/projects/{id}/stack/generate`

Returns immediately with a job status; the pipeline runs async. A follow-up `GET /api/projects/{id}/stack` returns current state including `is_generating: bool`.

### First-run

When a project is first added to Chronicler, the stack pipeline runs automatically as part of project initialization — before the first change log entry.

### UI

- "Regenerate Stack Sheet" button in the project detail view, alongside the existing "Generate Handoff" button
- Shows a spinner while generating
- Displays "Stack sheet last verified: X ago" timestamp
- Stale entries appear dimmed with a warning icon in a stack detail panel

---

## Staleness Detection

Runs as a lightweight check whenever the stack sheet is read (UI load or API call). Three checks:

1. **Manifest hash check** — hash current manifest files and compare to `manifest_hash` in the JSON. If different, mark sheet as stale and show: *"Stack sheet may be outdated — `package.json` changed since last scan."*

2. **Entry age check** — any entry where `last_verified` is older than a configurable threshold (default: 30 days) gets `"stale": true`. Shown dimmed in UI.

3. **Missing category detection** — heuristic rules with no LLM cost. Examples: if `tailwind.config.js` exists but no color entries are present, flag as a gap. If `package.json` has `lucide-react` but no icons entry exists, flag it.

Staleness is surfaced as warnings only — never auto-fixed. Agents reading `STACK.md` see a warning header when stale:

```markdown
> ⚠️ Last verified: 2026-03-01. Some entries may be outdated — run `chronicler stack regenerate` or use the UI.
```

---

## New Module Structure

```
chronicler/
  stack/
    __init__.py
    extractor.py      # Stage 1: static manifest parsers
    enricher.py       # Stage 2: LLM enrichment
    renderer.py       # JSON → STACK.md
    staleness.py      # Staleness check logic
    schema.py         # StackEntry, TechStack Pydantic models
```

New API endpoints:
- `POST /api/projects/{id}/stack/generate` — trigger regeneration
- `GET /api/projects/{id}/stack` — get current stack sheet + staleness state

New CLI command:
- `chronicler stack regenerate [project-path]` — trigger from terminal

---

## Out of Scope

- Automatic constraint generation (LLM suggests constraints, human approves — not in this spec)
- Cross-project stack comparisons
- Stack sheet versioning / history
