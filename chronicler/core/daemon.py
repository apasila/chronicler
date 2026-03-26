from __future__ import annotations
import os
import signal
import subprocess
from pathlib import Path


def get_daemon_status(project_path: Path) -> str:
    """Returns 'running' if daemon is alive, 'stopped' otherwise."""
    pid_file = project_path / ".chronicler" / "chronicler.pid"
    if not pid_file.exists():
        return "stopped"
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)  # signal 0 = existence check only
        return "running"
    except (ProcessLookupError, ValueError, PermissionError):
        pid_file.unlink(missing_ok=True)
        return "stopped"


def start_daemon(project_path: Path) -> None:
    """Launch watcher as a detached background process."""
    proc = subprocess.Popen(
        ["chronicler", "start", "--foreground", "--path", str(project_path)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    pid_file = project_path / ".chronicler" / "chronicler.pid"
    pid_file.write_text(str(proc.pid))


def stop_daemon(project_path: Path) -> None:
    """Send SIGTERM to daemon and remove PID file."""
    pid_file = project_path / ".chronicler" / "chronicler.pid"
    if not pid_file.exists():
        return
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, ValueError):
        pass
    pid_file.unlink(missing_ok=True)
