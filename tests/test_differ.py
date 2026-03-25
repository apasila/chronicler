# tests/test_differ.py
import pytest
from chronicler.core.differ import Differ, DiffResult

@pytest.fixture
def tmp_project(tmp_path):
    return tmp_path

def test_raw_diff_new_file(tmp_project):
    f = tmp_project / "hello.py"
    f.write_text("def hello():\n    return 'world'\n")
    differ = Differ(project_path=str(tmp_project), git_enabled=False)
    result = differ.diff_file(str(f))
    assert result is not None
    assert result.lines_added > 0
    assert result.lines_removed == 0
    assert "hello" in result.diff_text

def test_raw_diff_modified_file(tmp_project):
    f = tmp_project / "app.py"
    f.write_text("x = 1\n")
    differ = Differ(project_path=str(tmp_project), git_enabled=False)
    differ.store_snapshot(str(f))
    f.write_text("x = 1\ny = 2\n")
    result = differ.diff_file(str(f))
    assert result.lines_added == 1
    assert "y = 2" in result.diff_text

def test_raw_diff_deleted_lines(tmp_project):
    f = tmp_project / "app.py"
    f.write_text("a = 1\nb = 2\nc = 3\n")
    differ = Differ(project_path=str(tmp_project), git_enabled=False)
    differ.store_snapshot(str(f))
    f.write_text("a = 1\n")
    result = differ.diff_file(str(f))
    assert result.lines_removed == 2

def test_detect_language(tmp_project):
    differ = Differ(project_path=str(tmp_project), git_enabled=False)
    assert differ.detect_language("app.py") == "python"
    assert differ.detect_language("index.ts") == "typescript"
    assert differ.detect_language("main.go") == "go"
    assert differ.detect_language("unknown.xyz") == "unknown"
