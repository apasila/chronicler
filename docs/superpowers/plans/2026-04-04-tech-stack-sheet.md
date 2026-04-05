# Tech Stack Sheet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-generate and maintain a `.chronicler/tech-stack.json` + `STACK.md` per project so coding agents always know the established tech decisions.

**Architecture:** Two-stage pipeline (static extractor → LLM enricher) lives in a new `chronicler/stack/` module. The watcher auto-triggers on manifest file changes; a manual API endpoint and CLI command allow on-demand regeneration. A renderer converts the JSON to `STACK.md` in the project root for agent consumption.

**Tech Stack:** Python 3.11+, Pydantic v2, litellm (via existing `LLMClient`), FastAPI (existing), typer (existing), pytest

---

## File Map

**Create:**
- `chronicler/stack/__init__.py` — public `run_stack_pipeline(project_path, config)` function
- `chronicler/stack/schema.py` — `StackEntry`, `TechStack` Pydantic models
- `chronicler/stack/extractor.py` — Stage 1: deterministic manifest parsers
- `chronicler/stack/enricher.py` — Stage 2: LLM enrichment
- `chronicler/stack/renderer.py` — `TechStack` → `STACK.md`
- `chronicler/stack/staleness.py` — staleness check logic
- `tests/stack/__init__.py`
- `tests/stack/test_extractor.py`
- `tests/stack/test_renderer.py`
- `tests/stack/test_staleness.py`

**Modify:**
- `chronicler/llm/prompts.py` — add stack enricher system + user prompts, add version key
- `chronicler/llm/client.py` — add `"stack_enricher"` to `get_model_for_task`
- `chronicler/storage/schema.py` — extend `MAP_TRIGGER_PATTERNS` with `go.mod`, `tsconfig.json`, `tailwind.config.*`, `*.css`, `*.scss`
- `chronicler/ui/server.py` — add `GET /api/projects/{id}/stack` + `POST /api/projects/{id}/stack/generate`; trigger pipeline in `add_project`
- `chronicler/cli/main.py` — add `stack` Typer sub-app with `regenerate` command

---

## Task 1: Stack Schema

**Files:**
- Create: `chronicler/stack/schema.py`
- Create: `chronicler/stack/__init__.py`
- Create: `tests/stack/__init__.py`
- Create: `tests/stack/test_extractor.py` (stub only — filled in Task 2)

- [ ] **Step 1: Create `chronicler/stack/schema.py`**

```python
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel

STACK_CATEGORIES = [
    "language", "runtime", "framework", "library",
    "service", "font", "color", "icons", "tooling", "devops",
]


class StackEntry(BaseModel):
    key: str
    category: str
    value: str
    source: str          # e.g. "package.json", "llm_inference"
    confidence: float    # 0.0–1.0
    detected_at: datetime
    last_verified: datetime
    reason: str | None = None   # populated only for llm_inference entries


class TechStack(BaseModel):
    generated_at: datetime
    manifest_hash: str           # SHA-256 of all manifest file contents concatenated
    entries: list[StackEntry]
    constraints: list[str] = []  # human-authored, survives regeneration
```

- [ ] **Step 2: Create `chronicler/stack/__init__.py` (empty for now)**

```python
from __future__ import annotations
```

- [ ] **Step 3: Create `tests/stack/__init__.py`**

```python
```

- [ ] **Step 4: Commit**

```bash
git add chronicler/stack/schema.py chronicler/stack/__init__.py tests/stack/__init__.py
git commit -m "feat: add TechStack and StackEntry schema"
```

---

## Task 2: Static Extractor

**Files:**
- Create: `chronicler/stack/extractor.py`
- Create: `tests/stack/test_extractor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/stack/test_extractor.py
from __future__ import annotations
import json
from pathlib import Path
import pytest
from chronicler.stack.extractor import extract_stack, _hash_manifests


@pytest.fixture
def project_dir(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "dependencies": {"react": "^18.2.0", "zustand": "^4.5.0"},
        "devDependencies": {"typescript": "^5.4.0"},
        "engines": {"node": ">=20"}
    }))
    (tmp_path / "tsconfig.json").write_text(json.dumps({
        "compilerOptions": {"target": "ES2022", "strict": True}
    }))
    # Tailwind config with theme colors
    (tmp_path / "tailwind.config.js").write_text(
        "module.exports = { theme: { extend: { colors: { brand: '#e94560', bg: '#1a1a2e' } } } }"
    )
    (tmp_path / ".env.example").write_text(
        "STRIPE_API_KEY=\nSENDGRID_API_KEY=\nFOO=bar\n"
    )
    return tmp_path


def test_extract_libraries_from_package_json(project_dir):
    stack = extract_stack(project_dir)
    keys = [e.key for e in stack.entries]
    assert "react" in keys
    assert "zustand" in keys
    assert "typescript" in keys


def test_library_versions_from_package_json(project_dir):
    stack = extract_stack(project_dir)
    react = next(e for e in stack.entries if e.key == "react")
    assert react.value == "^18.2.0"
    assert react.source == "package.json"
    assert react.confidence == 1.0
    assert react.reason is None


def test_runtime_from_engines(project_dir):
    stack = extract_stack(project_dir)
    node = next((e for e in stack.entries if e.key == "node"), None)
    assert node is not None
    assert node.category == "runtime"
    assert node.value == ">=20"


def test_language_from_tsconfig(project_dir):
    stack = extract_stack(project_dir)
    ts = next((e for e in stack.entries if e.key == "typescript-target"), None)
    assert ts is not None
    assert ts.category == "language"
    assert ts.value == "ES2022"


def test_services_from_env_example(project_dir):
    stack = extract_stack(project_dir)
    keys = [e.key for e in stack.entries if e.category == "service"]
    assert "stripe" in keys
    assert "sendgrid" in keys
    assert "foo" not in keys  # generic key, not a known service


def test_manifest_hash_is_stable(project_dir):
    h1 = _hash_manifests(project_dir)
    h2 = _hash_manifests(project_dir)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_manifest_hash_changes_on_edit(project_dir):
    h1 = _hash_manifests(project_dir)
    (project_dir / "package.json").write_text(json.dumps({"dependencies": {"react": "^19.0.0"}}))
    h2 = _hash_manifests(project_dir)
    assert h1 != h2


def test_missing_manifests_returns_empty_entries(tmp_path):
    stack = extract_stack(tmp_path)
    assert stack.entries == []
    assert stack.manifest_hash == _hash_manifests(tmp_path)
```

- [ ] **Step 2: Run tests — verify they all fail**

```bash
cd /Users/anttipasila/Desktop/chronicler
pytest tests/stack/test_extractor.py -v
```

Expected: all tests fail with `ImportError` or `ModuleNotFoundError`.

- [ ] **Step 3: Create `chronicler/stack/extractor.py`**

```python
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import toml

from chronicler.stack.schema import StackEntry, TechStack, STACK_CATEGORIES

# Known service patterns: env var prefix → service name
_SERVICE_PATTERNS = {
    "stripe": "stripe",
    "sendgrid": "sendgrid",
    "twilio": "twilio",
    "mailgun": "mailgun",
    "aws": "aws",
    "gcp": "gcp",
    "azure": "azure",
    "openai": "openai",
    "anthropic": "anthropic",
    "groq": "groq",
    "gemini": "gemini",
    "sentry": "sentry",
    "datadog": "datadog",
    "segment": "segment",
    "mixpanel": "mixpanel",
    "amplitude": "amplitude",
    "pusher": "pusher",
    "cloudinary": "cloudinary",
    "algolia": "algolia",
    "supabase": "supabase",
    "firebase": "firebase",
    "mongo": "mongodb",
    "redis": "redis",
    "postgres": "postgresql",
    "mysql": "mysql",
    "planetscale": "planetscale",
    "neon": "neon",
    "vercel": "vercel",
    "netlify": "netlify",
    "github": "github",
    "slack": "slack",
    "discord": "discord",
    "telegram": "telegram",
    "twitch": "twitch",
    "spotify": "spotify",
    "google": "google",
    "facebook": "facebook",
    "twitter": "twitter",
    "paypal": "paypal",
    "braintree": "braintree",
    "fish_audio": "fish-audio",
    "kokoro": "kokoro",
    "polygon": "polygon",
}

_MANIFEST_GLOBS = [
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "tsconfig.json",
    "tailwind.config.js",
    "tailwind.config.ts",
    "tailwind.config.mjs",
    ".env.example",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_manifests(project_path: Path) -> str:
    """SHA-256 of all manifest file contents, sorted by name for stability."""
    h = hashlib.sha256()
    found = []
    for glob in _MANIFEST_GLOBS:
        for p in sorted(project_path.glob(glob)):
            if p.is_file():
                found.append(p)
    for p in sorted(found, key=lambda x: x.name):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def _entry(key: str, category: str, value: str, source: str) -> StackEntry:
    now = _now()
    return StackEntry(
        key=key, category=category, value=value,
        source=source, confidence=1.0,
        detected_at=now, last_verified=now,
    )


def _parse_package_json(path: Path) -> list[StackEntry]:
    entries: list[StackEntry] = []
    try:
        data = json.loads(path.read_text())
    except Exception:
        return entries

    for section in ("dependencies", "devDependencies", "peerDependencies"):
        for name, version in (data.get(section) or {}).items():
            entries.append(_entry(name, "library", str(version), "package.json"))

    engines = data.get("engines") or {}
    for runtime, version in engines.items():
        entries.append(_entry(runtime, "runtime", str(version), "package.json"))

    return entries


def _parse_tsconfig(path: Path) -> list[StackEntry]:
    entries: list[StackEntry] = []
    try:
        data = json.loads(path.read_text())
    except Exception:
        return entries
    opts = data.get("compilerOptions") or {}
    if "target" in opts:
        entries.append(_entry("typescript-target", "language", str(opts["target"]), "tsconfig.json"))
    return entries


def _parse_pyproject(path: Path) -> list[StackEntry]:
    entries: list[StackEntry] = []
    try:
        data = toml.loads(path.read_text())
    except Exception:
        return entries
    deps = (data.get("project") or {}).get("dependencies") or []
    for dep in deps:
        # dep may be "requests>=2.28" — extract name
        name = re.split(r"[><=!~\s\[]", dep)[0].strip()
        entries.append(_entry(name, "library", dep, "pyproject.toml"))
    return entries


def _parse_requirements(path: Path) -> list[StackEntry]:
    entries: list[StackEntry] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        name = re.split(r"[><=!~\s\[]", line)[0].strip()
        if name:
            entries.append(_entry(name, "library", line, "requirements.txt"))
    return entries


def _parse_cargo(path: Path) -> list[StackEntry]:
    entries: list[StackEntry] = []
    try:
        data = toml.loads(path.read_text())
    except Exception:
        return entries
    for section in ("dependencies", "dev-dependencies", "build-dependencies"):
        for name, spec in (data.get(section) or {}).items():
            version = spec if isinstance(spec, str) else (spec.get("version") or "")
            entries.append(_entry(name, "library", version, "Cargo.toml"))
    return entries


def _parse_go_mod(path: Path) -> list[StackEntry]:
    entries: list[StackEntry] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("require ") and " " in line:
            parts = line.split()
            if len(parts) >= 3:
                entries.append(_entry(parts[1], "library", parts[2], "go.mod"))
        elif not line.startswith("//") and not line.startswith("module") and not line.startswith("go "):
            parts = line.split()
            if len(parts) == 2 and "/" in parts[0]:
                entries.append(_entry(parts[0], "library", parts[1], "go.mod"))
    return entries


def _parse_tailwind(path: Path) -> list[StackEntry]:
    """Extract color hex values from tailwind config using regex (no JS eval)."""
    entries: list[StackEntry] = []
    text = path.read_text()
    # Find hex colors
    for match in re.finditer(r"'#([0-9a-fA-F]{3,8})'|\"#([0-9a-fA-F]{3,8})\"", text):
        color = "#" + (match.group(1) or match.group(2))
        entries.append(_entry(color, "color", color, path.name))
    return entries


def _parse_env_example(path: Path) -> list[StackEntry]:
    entries: list[StackEntry] = []
    seen: set[str] = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=")[0].lower()
        for pattern, service in _SERVICE_PATTERNS.items():
            if pattern in key and service not in seen:
                seen.add(service)
                entries.append(_entry(service, "service", "detected", ".env.example"))
                break
    return entries


def extract_stack(project_path: Path) -> TechStack:
    """Run Stage 1: deterministic manifest parsing. Returns a TechStack."""
    entries: list[StackEntry] = []

    parsers = [
        ("package.json",      _parse_package_json),
        ("tsconfig.json",     _parse_tsconfig),
        ("pyproject.toml",    _parse_pyproject),
        ("requirements.txt",  _parse_requirements),
        ("Cargo.toml",        _parse_cargo),
        ("go.mod",            _parse_go_mod),
        (".env.example",      _parse_env_example),
    ]
    for filename, parser in parsers:
        p = project_path / filename
        if p.exists():
            entries.extend(parser(p))

    # Tailwind config (multiple possible names)
    for tw_name in ("tailwind.config.js", "tailwind.config.ts", "tailwind.config.mjs"):
        p = project_path / tw_name
        if p.exists():
            entries.extend(_parse_tailwind(p))
            break

    return TechStack(
        generated_at=datetime.now(timezone.utc),
        manifest_hash=_hash_manifests(project_path),
        entries=entries,
        constraints=[],
    )
```

- [ ] **Step 4: Run tests — verify they all pass**

```bash
pytest tests/stack/test_extractor.py -v
```

Expected: all 8 tests pass.

- [ ] **Step 5: Extend `MAP_TRIGGER_PATTERNS` in `chronicler/storage/schema.py`**

Find the existing `MAP_TRIGGER_PATTERNS` list (around line 16) and replace it with:

```python
MAP_TRIGGER_PATTERNS = [
    "package.json", "requirements.txt", "go.mod", "Cargo.toml",
    "pyproject.toml", "tsconfig.json",
    "tailwind.config.js", "tailwind.config.ts", "tailwind.config.mjs",
    ".env.example",
    "*.routes.*", "router.*", "app/api/**",
    "*.config.*", "README*",
]
```

- [ ] **Step 6: Commit**

```bash
git add chronicler/stack/extractor.py chronicler/storage/schema.py tests/stack/test_extractor.py
git commit -m "feat: add static manifest extractor (Stage 1)"
```

---

## Task 3: LLM Enricher

**Files:**
- Create: `chronicler/stack/enricher.py`
- Modify: `chronicler/llm/prompts.py`
- Modify: `chronicler/llm/client.py`

- [ ] **Step 1: Add stack enricher prompt to `chronicler/llm/prompts.py`**

Add to the `PROMPT_VERSIONS` dict:

```python
PROMPT_VERSIONS = {
    "entry_classifier":   "1.0",
    "session_summarizer": "1.0",
    "map_updater":        "1.0",
    "handoff_generator":  "1.0",
    "stack_enricher":     "1.0",   # ← add this line
}
```

Then add these two constants at the end of the file:

```python
SYSTEM_PROMPT_STACK_ENRICHER = """
You are Chronicler's stack analyser. You receive a list of already-detected
tech stack entries (from static manifest parsing) and a sample of source files
from the project. Your job is to enrich the stack by detecting things that
static parsing misses.

You must return ONLY valid JSON. No explanation, no markdown, no preamble.

Return an array of new entries NOT already in the detected list. Each entry:
{{
  "key":        "string — library name, service name, font name, etc.",
  "category":   "language|runtime|framework|library|service|font|color|icons|tooling|devops",
  "value":      "string — version if known, otherwise 'active' or a short descriptor",
  "confidence": 0.0–1.0,
  "reason":     "string — one sentence explaining the evidence (e.g. 'found in 14 imports across 8 files')"
}}

Focus on:
- Icon packages (e.g. lucide-react, heroicons, react-icons) visible in imports
- Fonts loaded via CSS @import or link tags
- CSS design tokens (colors, spacing) not in tailwind.config
- 3rd party services used in code but not in .env.example
- Which installed libraries are actively imported vs just installed

Do NOT duplicate entries already in the detected list.
Return [] if you find nothing new.
"""

USER_PROMPT_STACK_ENRICHER = """
Project: {project_name}
Framework: {framework}

Already detected entries:
{detected_entries}

Source file samples (filename then content):
{source_samples}

Return new stack entries as a JSON array.
"""
```

- [ ] **Step 2: Add `stack_enricher` task to `chronicler/llm/client.py`**

Replace the `get_model_for_task` function:

```python
def get_model_for_task(task: str, config: Config) -> str:
    return {
        "entry_classifier":   config.models.workhorse,
        "session_summarizer": config.models.workhorse,
        "map_updater":        config.models.workhorse,
        "handoff_generator":  config.models.premium,
        "stack_enricher":     config.models.workhorse,
    }[task]
```

- [ ] **Step 3: Create `chronicler/stack/enricher.py`**

```python
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

from chronicler.config.settings import Config
from chronicler.llm.client import LLMClient
from chronicler.llm.prompts import (
    SYSTEM_PROMPT_STACK_ENRICHER,
    USER_PROMPT_STACK_ENRICHER,
    PROMPT_VERSIONS,
)
from chronicler.stack.schema import StackEntry, TechStack

# Source file extensions worth sampling
_SOURCE_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs",
    ".py", ".rs", ".go",
    ".css", ".scss", ".sass",
    ".vue", ".svelte",
}

_MAX_SAMPLE_FILES = 20
_MAX_FILE_CHARS = 2000


def _collect_source_samples(project_path: Path, existing_entries: list[StackEntry]) -> str:
    """Return up to _MAX_SAMPLE_FILES source files, prioritised by import count."""
    existing_keys = {e.key for e in existing_entries}
    candidates: list[tuple[int, Path]] = []

    for p in project_path.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in _SOURCE_EXTENSIONS:
            continue
        # Skip common noise dirs
        parts = p.parts
        if any(d in parts for d in ("node_modules", ".git", "__pycache__", ".venv", "dist", "build", ".chronicler")):
            continue
        try:
            text = p.read_text(errors="replace")
        except OSError:
            continue
        import_count = text.count("import ") + text.count("from ") + text.count("require(")
        candidates.append((import_count, p))

    candidates.sort(key=lambda x: x[0], reverse=True)
    samples: list[str] = []
    for _, p in candidates[:_MAX_SAMPLE_FILES]:
        try:
            content = p.read_text(errors="replace")[:_MAX_FILE_CHARS]
            rel = str(p.relative_to(project_path))
            samples.append(f"### {rel}\n{content}")
        except OSError:
            continue

    return "\n\n".join(samples)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end = -1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end])
    return text


def enrich_stack(
    stack: TechStack,
    project_path: Path,
    project_name: str,
    framework: str | None,
    config: Config,
) -> TechStack:
    """Run Stage 2: LLM enrichment. Returns a new TechStack with enriched entries merged in."""
    client = LLMClient(config)

    detected_summary = json.dumps(
        [{"key": e.key, "category": e.category, "value": e.value} for e in stack.entries],
        indent=2,
    )
    source_samples = _collect_source_samples(project_path, stack.entries)

    user_prompt = USER_PROMPT_STACK_ENRICHER.format(
        project_name=project_name,
        framework=framework or "unknown",
        detected_entries=detected_summary,
        source_samples=source_samples or "(no source files found)",
    )

    try:
        text, _tokens, _ms = client.complete(
            task="stack_enricher",
            system_prompt=SYSTEM_PROMPT_STACK_ENRICHER,
            user_prompt=user_prompt,
            temperature=0.1,
        )
        raw = json.loads(_strip_fences(text))
    except Exception:
        # LLM failure is non-fatal — return original stack unchanged
        return stack

    if not isinstance(raw, list):
        return stack

    now = datetime.now(timezone.utc)
    new_entries = list(stack.entries)
    existing_keys = {e.key for e in stack.entries}

    for item in raw:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", "")).strip()
        category = str(item.get("category", "library")).strip()
        value = str(item.get("value", "active")).strip()
        confidence = float(item.get("confidence", 0.7))
        reason = str(item.get("reason", "")).strip() or None

        if not key or key in existing_keys:
            continue

        new_entries.append(StackEntry(
            key=key, category=category, value=value,
            source="llm_inference", confidence=confidence,
            detected_at=now, last_verified=now,
            reason=reason,
        ))
        existing_keys.add(key)

    return TechStack(
        generated_at=stack.generated_at,
        manifest_hash=stack.manifest_hash,
        entries=new_entries,
        constraints=stack.constraints,
    )
```

- [ ] **Step 4: Commit**

```bash
git add chronicler/stack/enricher.py chronicler/llm/prompts.py chronicler/llm/client.py
git commit -m "feat: add LLM enricher (Stage 2) and stack_enricher prompt"
```

---

## Task 4: Renderer

**Files:**
- Create: `chronicler/stack/renderer.py`
- Create: `tests/stack/test_renderer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/stack/test_renderer.py
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from chronicler.stack.schema import StackEntry, TechStack
from chronicler.stack.renderer import render_stack_md, save_stack_json, load_stack_json


def _entry(key, category, value, source="package.json", confidence=1.0, reason=None):
    now = datetime.now(timezone.utc)
    return StackEntry(
        key=key, category=category, value=value,
        source=source, confidence=confidence,
        detected_at=now, last_verified=now,
        reason=reason,
    )


@pytest.fixture
def simple_stack():
    return TechStack(
        generated_at=datetime(2026, 4, 4, tzinfo=timezone.utc),
        manifest_hash="abc123",
        entries=[
            _entry("typescript", "language", "5.4.0"),
            _entry("react", "library", "^18.2.0"),
            _entry("stripe", "service", "detected"),
            _entry("lucide-react", "icons", "active", source="llm_inference",
                   confidence=0.9, reason="found in 14 imports"),
        ],
        constraints=["Do not add Redux — Zustand is the state manager"],
    )


def test_render_contains_inventory_header(simple_stack):
    md = render_stack_md(simple_stack, is_stale=False)
    assert "# Tech Stack" in md
    assert "Last verified" in md


def test_render_no_stale_warning_when_fresh(simple_stack):
    md = render_stack_md(simple_stack, is_stale=False)
    assert "⚠️" not in md


def test_render_stale_warning_when_stale(simple_stack):
    md = render_stack_md(simple_stack, is_stale=True)
    assert "⚠️" in md
    assert "outdated" in md.lower()


def test_render_contains_entries(simple_stack):
    md = render_stack_md(simple_stack, is_stale=False)
    assert "typescript" in md
    assert "react" in md
    assert "stripe" in md
    assert "lucide-react" in md


def test_render_constraints_section(simple_stack):
    md = render_stack_md(simple_stack, is_stale=False)
    assert "Decisions & Constraints" in md
    assert "Do not add Redux" in md


def test_render_no_constraints_section_when_empty():
    stack = TechStack(
        generated_at=datetime(2026, 4, 4, tzinfo=timezone.utc),
        manifest_hash="abc",
        entries=[_entry("react", "library", "18")],
        constraints=[],
    )
    md = render_stack_md(stack, is_stale=False)
    assert "Decisions & Constraints" not in md


def test_save_and_load_roundtrip(tmp_path, simple_stack):
    stack_dir = tmp_path / ".chronicler"
    stack_dir.mkdir()
    save_stack_json(simple_stack, tmp_path)
    loaded = load_stack_json(tmp_path)
    assert loaded is not None
    assert loaded.manifest_hash == simple_stack.manifest_hash
    assert len(loaded.entries) == len(simple_stack.entries)
    assert loaded.constraints == simple_stack.constraints


def test_load_stack_json_returns_none_when_missing(tmp_path):
    assert load_stack_json(tmp_path) is None


def test_save_preserves_constraints_on_overwrite(tmp_path, simple_stack):
    """Saving a stack with empty constraints preserves existing constraints from disk."""
    stack_dir = tmp_path / ".chronicler"
    stack_dir.mkdir()
    save_stack_json(simple_stack, tmp_path)

    # Now save a new stack without constraints — should inherit from existing
    new_stack = TechStack(
        generated_at=datetime(2026, 4, 4, tzinfo=timezone.utc),
        manifest_hash="xyz",
        entries=[_entry("vue", "framework", "3")],
        constraints=[],  # empty — should be filled from existing file
    )
    save_stack_json(new_stack, tmp_path)
    loaded = load_stack_json(tmp_path)
    assert loaded.constraints == simple_stack.constraints
```

- [ ] **Step 2: Run tests — verify they all fail**

```bash
pytest tests/stack/test_renderer.py -v
```

Expected: all fail with `ImportError`.

- [ ] **Step 3: Create `chronicler/stack/renderer.py`**

```python
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

from chronicler.stack.schema import StackEntry, TechStack

_CATEGORY_HEADINGS = {
    "language":  "Languages",
    "runtime":   "Runtime",
    "framework": "Frameworks",
    "library":   "Libraries",
    "service":   "Services",
    "font":      "Fonts",
    "color":     "Colors",
    "icons":     "Icons",
    "tooling":   "Tooling",
    "devops":    "DevOps",
}

_STACK_JSON_PATH = ".chronicler/tech-stack.json"
_STACK_MD_PATH = "STACK.md"


def render_stack_md(stack: TechStack, is_stale: bool) -> str:
    lines: list[str] = ["# Tech Stack", ""]

    if is_stale:
        lines += [
            "> ⚠️ Last verified: "
            + stack.generated_at.strftime("%Y-%m-%d")
            + ". Some entries may be outdated — regenerate via the Chronicler UI or run `chronicler stack regenerate`.",
            "",
        ]
    else:
        lines += [f"> Last verified: {stack.generated_at.strftime('%Y-%m-%d')}", ""]

    # Group entries by category
    by_category: dict[str, list[StackEntry]] = {}
    for entry in stack.entries:
        by_category.setdefault(entry.category, []).append(entry)

    for category, heading in _CATEGORY_HEADINGS.items():
        entries = by_category.get(category)
        if not entries:
            continue
        lines += [f"## {heading}", ""]
        lines += ["| Name | Value | Source | Confidence |",
                  "|------|-------|--------|------------|"]
        for e in sorted(entries, key=lambda x: x.key):
            confidence_str = "✓" if e.confidence == 1.0 else f"{e.confidence:.0%}"
            source = e.source
            lines.append(f"| {e.key} | {e.value} | {source} | {confidence_str} |")
        lines.append("")

    if stack.constraints:
        lines += ["## Decisions & Constraints", ""]
        for constraint in stack.constraints:
            lines.append(f"- {constraint}")
        lines.append("")

    return "\n".join(lines)


def save_stack_json(stack: TechStack, project_path: Path) -> None:
    """Write stack to .chronicler/tech-stack.json, preserving existing constraints."""
    json_path = project_path / _STACK_JSON_PATH

    # Preserve constraints from existing file if new stack has none
    existing_constraints = stack.constraints
    if not existing_constraints and json_path.exists():
        try:
            existing = json.loads(json_path.read_text())
            existing_constraints = existing.get("constraints", [])
        except Exception:
            pass

    final = TechStack(
        generated_at=stack.generated_at,
        manifest_hash=stack.manifest_hash,
        entries=stack.entries,
        constraints=existing_constraints,
    )

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(final.model_dump(mode="json"), indent=2, default=str)
    )


def load_stack_json(project_path: Path) -> TechStack | None:
    """Load stack from .chronicler/tech-stack.json, or None if not found."""
    json_path = project_path / _STACK_JSON_PATH
    if not json_path.exists():
        return None
    try:
        return TechStack.model_validate(json.loads(json_path.read_text()))
    except Exception:
        return None


def write_stack_md(stack: TechStack, project_path: Path, is_stale: bool) -> None:
    """Write STACK.md to the project root."""
    md = render_stack_md(stack, is_stale=is_stale)
    (project_path / _STACK_MD_PATH).write_text(md)
```

- [ ] **Step 4: Run tests — verify they all pass**

```bash
pytest tests/stack/test_renderer.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add chronicler/stack/renderer.py tests/stack/test_renderer.py
git commit -m "feat: add stack renderer — JSON to STACK.md"
```

---

## Task 5: Staleness Checker

**Files:**
- Create: `chronicler/stack/staleness.py`
- Create: `tests/stack/test_staleness.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/stack/test_staleness.py
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from chronicler.stack.schema import StackEntry, TechStack
from chronicler.stack.staleness import check_staleness, StalenessResult


def _entry(key, category="library", value="1.0", source="package.json",
           days_old=0, confidence=1.0):
    now = datetime.now(timezone.utc)
    t = now - timedelta(days=days_old)
    return StackEntry(
        key=key, category=category, value=value, source=source,
        confidence=confidence, detected_at=t, last_verified=t,
    )


def _stack(entries, manifest_hash="abc123"):
    return TechStack(
        generated_at=datetime.now(timezone.utc),
        manifest_hash=manifest_hash,
        entries=entries,
        constraints=[],
    )


def test_fresh_stack_not_stale(tmp_path):
    (tmp_path / "package.json").write_text('{"dependencies": {}}')
    stack = _stack([_entry("react")])
    # patch manifest_hash to match current
    from chronicler.stack.extractor import _hash_manifests
    stack = TechStack(**{**stack.model_dump(), "manifest_hash": _hash_manifests(tmp_path)})
    result = check_staleness(stack, tmp_path)
    assert not result.is_stale


def test_manifest_hash_mismatch_is_stale(tmp_path):
    (tmp_path / "package.json").write_text('{"dependencies": {"react": "18"}}')
    stack = _stack([_entry("react")], manifest_hash="old_hash")
    result = check_staleness(stack, tmp_path)
    assert result.is_stale
    assert any("package.json" in r or "manifest" in r.lower() for r in result.reasons)


def test_old_entry_flagged_stale(tmp_path):
    stack = _stack([_entry("react", days_old=35)])
    result = check_staleness(stack, tmp_path, max_age_days=30)
    assert result.is_stale
    assert any("stale" in r.lower() or "old" in r.lower() or "react" in r for r in result.reasons)


def test_fresh_entry_not_flagged(tmp_path):
    from chronicler.stack.extractor import _hash_manifests
    stack = _stack([_entry("react", days_old=5)])
    stack = TechStack(**{**stack.model_dump(), "manifest_hash": _hash_manifests(tmp_path)})
    result = check_staleness(stack, tmp_path, max_age_days=30)
    assert not result.is_stale


def test_missing_category_detected(tmp_path):
    (tmp_path / "tailwind.config.js").write_text(
        "module.exports = { theme: { colors: { brand: '#e94560' } } }"
    )
    # Stack has no color entries even though tailwind.config.js exists
    stack = _stack([_entry("react")])
    result = check_staleness(stack, tmp_path)
    assert any("color" in r.lower() or "tailwind" in r.lower() for r in result.reasons)
```

- [ ] **Step 2: Run tests — verify they all fail**

```bash
pytest tests/stack/test_staleness.py -v
```

Expected: all fail with `ImportError`.

- [ ] **Step 3: Create `chronicler/stack/staleness.py`**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from chronicler.stack.extractor import _hash_manifests
from chronicler.stack.schema import TechStack

_DEFAULT_MAX_AGE_DAYS = 30

# Heuristic: if this file exists but the category has no entries, flag it
_CATEGORY_HINTS: list[tuple[str, str, str]] = [
    # (glob, category_that_should_exist, human_readable_note)
    ("tailwind.config*", "color", "tailwind.config.* found but no color entries"),
    ("tailwind.config*", "font", "tailwind.config.* found but no font entries"),
    (".env.example",      "service", ".env.example found but no service entries"),
]


@dataclass
class StalenessResult:
    is_stale: bool
    reasons: list[str] = field(default_factory=list)


def check_staleness(
    stack: TechStack,
    project_path: Path,
    max_age_days: int = _DEFAULT_MAX_AGE_DAYS,
) -> StalenessResult:
    reasons: list[str] = []

    # 1. Manifest hash check
    current_hash = _hash_manifests(project_path)
    if current_hash != stack.manifest_hash:
        reasons.append(
            "Manifest files changed since last scan (manifest hash mismatch)"
        )

    # 2. Entry age check
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    stale_keys = [
        e.key for e in stack.entries
        if (
            e.last_verified.replace(tzinfo=timezone.utc)
            if e.last_verified.tzinfo is None
            else e.last_verified
        ) < cutoff
    ]
    if stale_keys:
        reasons.append(
            f"{len(stale_keys)} entries not verified in over {max_age_days} days: "
            + ", ".join(stale_keys[:5])
            + ("..." if len(stale_keys) > 5 else "")
        )

    # 3. Missing category detection
    existing_categories = {e.category for e in stack.entries}
    for glob, category, note in _CATEGORY_HINTS:
        if list(project_path.glob(glob)) and category not in existing_categories:
            reasons.append(note)

    return StalenessResult(is_stale=bool(reasons), reasons=reasons)
```

- [ ] **Step 4: Run tests — verify they all pass**

```bash
pytest tests/stack/test_staleness.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add chronicler/stack/staleness.py tests/stack/test_staleness.py
git commit -m "feat: add staleness checker"
```

---

## Task 6: Pipeline Orchestrator

**Files:**
- Modify: `chronicler/stack/__init__.py`

- [ ] **Step 1: Write the orchestrator in `chronicler/stack/__init__.py`**

```python
from __future__ import annotations
from pathlib import Path

from chronicler.config.settings import Config, load_config
from chronicler.stack.extractor import extract_stack
from chronicler.stack.enricher import enrich_stack
from chronicler.stack.renderer import load_stack_json, save_stack_json, write_stack_md
from chronicler.stack.staleness import check_staleness


def run_stack_pipeline(
    project_path: Path,
    project_name: str,
    framework: str | None,
    config: Config,
    skip_llm: bool = False,
) -> None:
    """Full two-stage pipeline: extract → enrich → save JSON → write STACK.md."""
    # Stage 1
    stack = extract_stack(project_path)

    # Stage 2 (optional — skip in tests or when LLM is unavailable)
    if not skip_llm:
        stack = enrich_stack(stack, project_path, project_name, framework, config)

    # Persist
    save_stack_json(stack, project_path)

    # Render
    staleness = check_staleness(stack, project_path)
    write_stack_md(stack, project_path, is_stale=staleness.is_stale)
```

- [ ] **Step 2: Run the full test suite to confirm nothing is broken**

```bash
pytest tests/ -v
```

Expected: all existing + new tests pass.

- [ ] **Step 3: Commit**

```bash
git add chronicler/stack/__init__.py
git commit -m "feat: add stack pipeline orchestrator"
```

---

## Task 7: API Endpoints + First-Run

**Files:**
- Modify: `chronicler/ui/server.py`

- [ ] **Step 1: Add stack imports at the top of `chronicler/ui/server.py`**

Add after the existing imports (around line 20):

```python
from chronicler.stack import run_stack_pipeline
from chronicler.stack.renderer import load_stack_json
from chronicler.stack.staleness import check_staleness
```

- [ ] **Step 2: Add `GET /api/projects/{project_id}/stack` endpoint**

Add after the existing `generate_handoff` endpoint (around line 320):

```python
    @app.get("/api/projects/{project_id}/stack")
    def get_stack(project_id: str):
        project = db.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        project_path = Path(project.path)
        stack = load_stack_json(project_path)
        if stack is None:
            return JSONResponse({"exists": False, "is_stale": False, "entries": [], "constraints": [], "reasons": []})
        staleness = check_staleness(stack, project_path)
        return JSONResponse({
            "exists": True,
            "generated_at": stack.generated_at.isoformat(),
            "is_stale": staleness.is_stale,
            "reasons": staleness.reasons,
            "entries": [e.model_dump(mode="json") for e in stack.entries],
            "constraints": stack.constraints,
        })
```

- [ ] **Step 3: Add `POST /api/projects/{project_id}/stack/generate` endpoint**

Add immediately after the `get_stack` endpoint:

```python
    @app.post("/api/projects/{project_id}/stack/generate")
    def generate_stack(project_id: str):
        project = db.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        project_path = Path(project.path)
        try:
            config = load_config(str(project_path))
            run_stack_pipeline(
                project_path=project_path,
                project_name=project.name,
                framework=project.framework,
                config=config,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Stack generation failed: {e}")
        stack = load_stack_json(project_path)
        return JSONResponse({
            "status": "generated",
            "generated_at": stack.generated_at.isoformat() if stack else None,
            "entry_count": len(stack.entries) if stack else 0,
        })
```

- [ ] **Step 4: Trigger stack pipeline on first project add**

In the `add_project` endpoint, find the line that returns (around line 147):

```python
        return {"id": project_id, "name": req.name, "path": str(project_path), "framework": framework}
```

Replace it with:

```python
        # Generate initial stack sheet in background (non-fatal if it fails)
        try:
            config = load_config(str(project_path))
            run_stack_pipeline(
                project_path=project_path,
                project_name=req.name,
                framework=framework or None,
                config=config,
            )
        except Exception:
            pass  # stack sheet is optional — don't block project creation

        return {"id": project_id, "name": req.name, "path": str(project_path), "framework": framework}
```

- [ ] **Step 5: Start server and manually verify endpoints work**

```bash
cd /Users/anttipasila/Desktop/chronicler
chronicler ui
```

In another terminal:
```bash
# List projects to get an ID
curl -s http://localhost:8765/api/projects | python3 -m json.tool

# Get stack for a project (replace PROJECT_ID)
curl -s http://localhost:8765/api/projects/PROJECT_ID/stack | python3 -m json.tool

# Trigger generation
curl -s -X POST http://localhost:8765/api/projects/PROJECT_ID/stack/generate | python3 -m json.tool
```

Expected: `get_stack` returns `{"exists": true, ...}` after generation.

- [ ] **Step 6: Commit**

```bash
git add chronicler/ui/server.py
git commit -m "feat: add stack API endpoints and first-run generation"
```

---

## Task 8: CLI Command

**Files:**
- Modify: `chronicler/cli/main.py`

- [ ] **Step 1: Add stack sub-app and regenerate command to `chronicler/cli/main.py`**

Add after the existing imports at the top of the file:

```python
from chronicler.stack import run_stack_pipeline
from chronicler.stack.renderer import load_stack_json
from chronicler.stack.staleness import check_staleness
```

Add after the main `app` definition (around line 23):

```python
stack_app = typer.Typer(name="stack", help="Tech stack sheet commands")
app.add_typer(stack_app)
```

Add the regenerate command:

```python
@stack_app.command("regenerate")
def stack_regenerate(
    path: str = typer.Option(".", help="Project path"),
):
    """Regenerate the tech stack sheet for a project."""
    project_path = Path(path).resolve()
    if not project_path.exists():
        console.print(f"[red]Path does not exist: {project_path}[/red]")
        raise typer.Exit(1)

    db = _get_db()
    project = db.get_project_by_path(str(project_path))
    if project is None:
        console.print("[red]Project not registered with Chronicler. Run `chronicler init` first.[/red]")
        raise typer.Exit(1)

    console.print(f"Generating stack sheet for [bold]{project.name}[/bold]...")
    try:
        config = load_config(str(project_path))
        run_stack_pipeline(
            project_path=project_path,
            project_name=project.name,
            framework=project.framework,
            config=config,
        )
    except Exception as e:
        console.print(f"[red]Stack generation failed: {e}[/red]")
        raise typer.Exit(1)

    stack = load_stack_json(project_path)
    if stack:
        staleness = check_staleness(stack, project_path)
        table = Table(title="Tech Stack Sheet")
        table.add_column("Key", style="cyan")
        table.add_column("Category")
        table.add_column("Value")
        table.add_column("Source")
        for entry in sorted(stack.entries, key=lambda e: (e.category, e.key)):
            table.add_row(entry.key, entry.category, entry.value, entry.source)
        console.print(table)
        console.print(f"\n[green]✓ Stack sheet saved to {project_path}/STACK.md[/green]")
        if staleness.is_stale:
            for reason in staleness.reasons:
                console.print(f"[yellow]⚠ {reason}[/yellow]")
```

- [ ] **Step 2: Verify CLI command works**

```bash
cd /Users/anttipasila/Desktop/chronicler
chronicler stack regenerate --path .
```

Expected: table of stack entries printed, `STACK.md` written to current directory.

- [ ] **Step 3: Run full test suite one final time**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add chronicler/cli/main.py
git commit -m "feat: add chronicler stack regenerate CLI command"
```

---

## Task 9: Auto-Trigger on Manifest Change

**Files:**
- Modify: `chronicler/cli/main.py` (inside `_run_watcher`)

The `_run_watcher` function in `cli/main.py` already has a MAP_TRIGGER_PATTERNS check at lines 322–328. We add an analogous stack trigger immediately after it.

- [ ] **Step 1: Add stack pipeline trigger inside `_run_watcher`**

Find the block inside `on_change` (around line 322):

```python
            # Trigger map update if file matches MAP_TRIGGER_PATTERNS
            fname = Path(file_path).name
            if any(_fnmatch.fnmatch(fname, p) or _fnmatch.fnmatch(diff.relative_path, p)
                   for p in MAP_TRIGGER_PATTERNS):
                updates = map_updater.update(map_mgr.read(), [entry])
                if any(v for v in updates.values() if v):
                    map_mgr.update(updates)
```

Replace it with:

```python
            # Trigger map update if file matches MAP_TRIGGER_PATTERNS
            fname = Path(file_path).name
            is_manifest = any(
                _fnmatch.fnmatch(fname, p) or _fnmatch.fnmatch(diff.relative_path, p)
                for p in MAP_TRIGGER_PATTERNS
            )
            if is_manifest:
                updates = map_updater.update(map_mgr.read(), [entry])
                if any(v for v in updates.values() if v):
                    map_mgr.update(updates)

            # Trigger stack sheet regeneration on manifest file changes
            _STACK_MANIFEST_NAMES = {
                "package.json", "pyproject.toml", "requirements.txt",
                "Cargo.toml", "go.mod", "tsconfig.json",
                "tailwind.config.js", "tailwind.config.ts", "tailwind.config.mjs",
                ".env.example",
            }
            if fname in _STACK_MANIFEST_NAMES:
                try:
                    from chronicler.stack import run_stack_pipeline
                    run_stack_pipeline(
                        project_path=Path(project.path),
                        project_name=project.name,
                        framework=project.framework,
                        config=config,
                    )
                    console.print(f"[dim]  → stack sheet updated[/dim]")
                except Exception as stack_err:
                    console.print(f"[yellow]  → stack update failed: {stack_err}[/yellow]")
```

- [ ] **Step 2: Run full test suite to confirm nothing regressed**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add chronicler/cli/main.py
git commit -m "feat: auto-regenerate stack sheet when manifest files change"
```

---

## Task 10: UI Button (Frontend)

**Files:**
- Modify: `chronicler/ui/static/index.html`

- [ ] **Step 1: Find the Generate Handoff button in the UI**

```bash
grep -n "handoff\|Generate" /Users/anttipasila/Desktop/chronicler/chronicler/ui/static/index.html | head -20
```

Note the line number of the handoff button — the stack button goes right next to it.

- [ ] **Step 2: Read the section around the handoff button**

```bash
# Use the line number from Step 1 — read ±10 lines around it
```

- [ ] **Step 3: Add Alpine.js stack state and method to the component data**

Find the Alpine.js `data()` object in `index.html` and add:

```javascript
stackGenerating: false,
stackLastGenerated: null,
stackIsStale: false,
```

Add the method alongside `generateHandoff`:

```javascript
async generateStack(projectId) {
    this.stackGenerating = true;
    try {
        const res = await fetch(`/api/projects/${projectId}/stack/generate`, { method: 'POST' });
        const data = await res.json();
        this.stackLastGenerated = data.generated_at;
        this.stackIsStale = false;
    } catch (e) {
        console.error('Stack generation failed', e);
    } finally {
        this.stackGenerating = false;
    }
},
async loadStackStatus(projectId) {
    try {
        const res = await fetch(`/api/projects/${projectId}/stack`);
        const data = await res.json();
        this.stackLastGenerated = data.generated_at || null;
        this.stackIsStale = data.is_stale || false;
    } catch (e) {}
},
```

- [ ] **Step 4: Add the Regenerate Stack Sheet button next to the Generate Handoff button**

Immediately after the handoff button HTML, add:

```html
<button
  @click="generateStack(selectedProject.id)"
  :disabled="stackGenerating"
  class="px-3 py-1.5 text-sm rounded border border-stone-300 hover:bg-stone-100 disabled:opacity-50"
  style="font-family: inherit"
>
  <span x-show="!stackGenerating">Regenerate Stack Sheet</span>
  <span x-show="stackGenerating">Generating...</span>
</button>
<span x-show="stackLastGenerated" class="text-xs text-stone-500 ml-2"
  x-text="stackIsStale ? '⚠ Stack may be stale' : 'Stack up to date'">
</span>
```

- [ ] **Step 5: Call `loadStackStatus` when a project is selected**

Find where `selectedProject` is set (when user clicks a project row) and add:

```javascript
this.loadStackStatus(project.id);
```

- [ ] **Step 6: Manual test in browser**

```bash
chronicler ui
```

Open `http://localhost:8765`, select a project, click "Regenerate Stack Sheet", verify the button shows spinner then "Stack up to date".

- [ ] **Step 7: Commit**

```bash
git add chronicler/ui/static/index.html
git commit -m "feat: add Regenerate Stack Sheet button to project UI"
```

---

## Final Verification

- [ ] **Run full test suite**

```bash
cd /Users/anttipasila/Desktop/chronicler
pytest tests/ -v
```

Expected: all tests pass, zero failures.

- [ ] **Verify STACK.md is generated for a real project**

```bash
chronicler stack regenerate --path /Users/anttipasila/Desktop/Macro/apps/server
cat /Users/anttipasila/Desktop/Macro/apps/server/STACK.md
```

Expected: readable STACK.md with libraries, services, and a Last verified date.
