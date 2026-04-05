from __future__ import annotations
from pathlib import Path

from chronicler.config.settings import Config
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
