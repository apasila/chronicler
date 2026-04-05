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
