from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

from chronicler.config.settings import Config
from chronicler.llm.client import LLMClient
from chronicler.llm.prompts import (
    SYSTEM_PROMPT_STACK_ENRICHER,
    USER_PROMPT_STACK_ENRICHER,
)
from chronicler.stack.schema import StackEntry, TechStack

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
    candidates: list[tuple[int, Path]] = []

    for p in project_path.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in _SOURCE_EXTENSIONS:
            continue
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

        # Skip entries with invalid categories — don't let bad LLM output break the schema
        from chronicler.stack.schema import STACK_CATEGORIES
        if category not in STACK_CATEGORIES:
            continue

        # Clamp confidence to valid range
        confidence = max(0.0, min(1.0, confidence))

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
