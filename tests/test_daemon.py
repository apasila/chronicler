import os
import signal
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from chronicler.core.daemon import start_daemon, stop_daemon, get_daemon_status


@pytest.fixture
def project_dir(tmp_path):
    chronicler_dir = tmp_path / ".chronicler"
    chronicler_dir.mkdir()
    return tmp_path


def test_get_daemon_status_stopped_no_pid_file(project_dir):
    assert get_daemon_status(project_dir) == "stopped"


def test_get_daemon_status_stopped_stale_pid(project_dir):
    pid_file = project_dir / ".chronicler" / "chronicler.pid"
    pid_file.write_text("99999999")  # very unlikely to be a real PID
    assert get_daemon_status(project_dir) == "stopped"
    assert not pid_file.exists()  # stale file cleaned up


def test_get_daemon_status_running(project_dir):
    pid_file = project_dir / ".chronicler" / "chronicler.pid"
    pid_file.write_text(str(os.getpid()))  # current process is definitely alive
    assert get_daemon_status(project_dir) == "running"


def test_stop_daemon_no_pid_file(project_dir):
    # should not raise
    stop_daemon(project_dir)


def test_stop_daemon_removes_pid_file(project_dir):
    pid_file = project_dir / ".chronicler" / "chronicler.pid"
    pid_file.write_text(str(os.getpid()))
    with patch("os.kill") as mock_kill:
        stop_daemon(project_dir)
    mock_kill.assert_called_once_with(os.getpid(), signal.SIGTERM)
    assert not pid_file.exists()


def test_start_daemon_creates_pid_file(project_dir):
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        start_daemon(project_dir)
    pid_file = project_dir / ".chronicler" / "chronicler.pid"
    assert pid_file.read_text().strip() == "12345"
    mock_popen.assert_called_once()
    args = mock_popen.call_args[0][0]
    assert "--path" in args
    assert str(project_dir) in args
