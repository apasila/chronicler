import os
import pytest
from chronicler.config.settings import load_config

GLOBAL_TOML = """
[chronicler]
version = "1.0"
telemetry = false

[logging]
default_mode = "debounced"
session_gap_minutes = 30
debounce_seconds = 10

[models]
tier = "cloud"
workhorse = "groq/llama-3.3-70b-versatile"
premium = "groq/llama-3.3-70b-versatile"

[groq]
api_key = "env:GROQ_API_KEY"

[ollama]
enabled = false
base_url = "http://localhost:11434"
workhorse_model = "phi4"
premium_model = "phi4"

[ignore]
global_patterns = ["node_modules/**", ".git/**", "*.lock"]

[storage]
db_path = "~/.config/chronicler/chronicler.db"
max_db_size_mb = 500
"""

PROJECT_TOML = """
[project]
name = "my-app"
framework = "nextjs"
languages = ["typescript"]

[logging]
mode = "every_save"
session_gap_minutes = 60

[ignore]
patterns = ["src/generated/**"]
"""

@pytest.fixture
def config_dirs(tmp_path):
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    (global_dir / "config.toml").write_text(GLOBAL_TOML)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    chronicler_dir = project_dir / ".chronicler"
    chronicler_dir.mkdir()
    (chronicler_dir / "config.toml").write_text(PROJECT_TOML)
    return global_dir, project_dir

def test_load_global_defaults(config_dirs):
    global_dir, project_dir = config_dirs
    config = load_config(str(project_dir / "no_project"), global_config_dir=str(global_dir))
    assert config.logging.default_mode == "debounced"
    assert config.logging.debounce_seconds == 10

def test_project_overrides_global(config_dirs):
    global_dir, project_dir = config_dirs
    config = load_config(str(project_dir), global_config_dir=str(global_dir))
    assert config.logging.mode == "every_save"
    assert config.logging.debounce_seconds == 10  # not overridden

def test_env_overrides_everything(config_dirs, monkeypatch):
    global_dir, project_dir = config_dirs
    monkeypatch.setenv("GROQ_API_KEY", "test-key-123")
    config = load_config(str(project_dir), global_config_dir=str(global_dir))
    assert config.groq.api_key == "test-key-123"

def test_ignore_patterns_merged(config_dirs):
    global_dir, project_dir = config_dirs
    config = load_config(str(project_dir), global_config_dir=str(global_dir))
    assert "node_modules/**" in config.ignore.patterns
    assert "src/generated/**" in config.ignore.patterns
