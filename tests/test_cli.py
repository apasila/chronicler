from typer.testing import CliRunner
from pathlib import Path
from datetime import datetime
from chronicler.cli.main import app
from chronicler.storage.db import Database
from chronicler.storage.schema import Project

runner = CliRunner()


def test_help():
    """Test that --help shows the app name and description."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "chronicler" in result.output.lower()


def test_init_help():
    """Test that init --help works."""
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0


def test_status_not_initialized(tmp_path, monkeypatch):
    """Test status when project not initialized."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "init" in result.output.lower() or "not" in result.output.lower()


def test_init_creates_config(tmp_path, monkeypatch):
    """Test that init creates .chronicler/config.toml."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--name", "test-app", "--path", "."], input="1\n1\n")
    assert result.exit_code == 0
    assert (tmp_path / ".chronicler" / "config.toml").exists()


def test_init_creates_handoffs_dir(tmp_path, monkeypatch):
    """Test that init creates .chronicler/handoffs directory."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--name", "test-app", "--path", "."], input="1\n1\n")
    assert result.exit_code == 0
    assert (tmp_path / ".chronicler" / "handoffs").exists()


def test_status_after_init(tmp_path, monkeypatch):
    """Test status after init shows daemon stopped."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "--name", "test-app", "--path", "."], input="1\n1\n")
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "stopped" in result.output.lower() or "daemon" in result.output.lower()


def test_log_not_initialized(tmp_path, monkeypatch):
    """Test log command when project not initialized."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["log"])
    assert result.exit_code == 0
    assert "not" in result.output.lower() or "init" in result.output.lower()


def test_map_not_initialized(tmp_path, monkeypatch):
    """Test map command when project not initialized."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["map"])
    assert result.exit_code == 0


def test_stop_no_daemon(tmp_path, monkeypatch):
    """Test stop when no daemon is running."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "--name", "test-app", "--path", "."], input="1\n1\n")
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    assert "not running" in result.output.lower() or "no daemon" in result.output.lower()
