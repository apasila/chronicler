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

    new_stack = TechStack(
        generated_at=datetime(2026, 4, 4, tzinfo=timezone.utc),
        manifest_hash="xyz",
        entries=[_entry("vue", "framework", "3")],
        constraints=[],  # empty — should be filled from existing file
    )
    save_stack_json(new_stack, tmp_path)
    loaded = load_stack_json(tmp_path)
    assert loaded.constraints == simple_stack.constraints
