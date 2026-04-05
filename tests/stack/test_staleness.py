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
    stack = _stack([_entry("react")])
    result = check_staleness(stack, tmp_path)
    assert any("color" in r.lower() or "tailwind" in r.lower() for r in result.reasons)
