import time
from unittest.mock import Mock
import pytest
from chronicler.core.watcher import Watcher

@pytest.fixture
def tmp_project(tmp_path):
    return tmp_path

def test_ignore_patterns(tmp_project):
    w = Watcher(str(tmp_project), ignore_patterns=["node_modules/**", "*.log"],
                on_change=Mock(), debounce_seconds=0.05)
    assert w.should_ignore(str(tmp_project / "node_modules" / "lodash" / "index.js"))
    assert w.should_ignore(str(tmp_project / "app.log"))
    assert not w.should_ignore(str(tmp_project / "src" / "app.py"))

def test_start_and_stop(tmp_project):
    w = Watcher(str(tmp_project), ignore_patterns=[], on_change=Mock(), debounce_seconds=0.05)
    w.start()
    assert w.is_running()
    w.stop()
    assert not w.is_running()

def test_detects_file_change(tmp_project):
    callback = Mock()
    w = Watcher(str(tmp_project), ignore_patterns=[], on_change=callback, debounce_seconds=0.1)
    w.start()
    (tmp_project / "test_file.py").write_text("x = 1\n")
    time.sleep(0.5)
    w.stop()
    assert callback.call_count >= 1
