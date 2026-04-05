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
