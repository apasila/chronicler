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


def start_daemon(project_path: Path) -> str | None:
    """Launch watcher as a detached background process.

    Returns None on success, or an error string if the process exits immediately.
    """
    import time
    log_file = project_path / ".chronicler" / "daemon.log"
    log_fh = open(log_file, "a")
    proc = subprocess.Popen(
        ["chronicler", "start", "--foreground", "--path", str(project_path)],
        start_new_session=True,
        stdout=log_fh,
        stderr=log_fh,
    )
    log_fh.close()

    pid_file = project_path / ".chronicler" / "chronicler.pid"
    pid_file.write_text(str(proc.pid))

    # Give the process 0.6s to either start successfully or fail fast
    time.sleep(0.6)
    ret = proc.poll()
    if ret is not None:
        try:
            out = log_file.read_text().strip().splitlines()
            out_str = "\n".join(out[-20:])  # last 20 lines
        except Exception:
            out_str = ""
        pid_file.unlink(missing_ok=True)
        return out_str or f"Process exited immediately (code {ret})"
    return None


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
