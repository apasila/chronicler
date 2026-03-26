# Chronicler Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local web dashboard (`chronicler ui`) with FastAPI + Alpine.js that shows live project status, activity feed, full log, and generates handoffs — with a 4-step onboarding flow for non-developer users.

**Architecture:** FastAPI serves a single `index.html` (Alpine.js + Tailwind CDN) plus JSON API routes. Activity updates stream via SSE from a polling endpoint that watches SQLite for new `log_entries` rowids. Daemon start/stop is extracted into a shared `core/daemon.py` module used by both CLI and the API server.

**Tech Stack:** FastAPI, uvicorn, Alpine.js (CDN), Tailwind CSS (CDN), Server-Sent Events, SQLite rowid cursor

---

## File Structure

```
# New files
chronicler/core/daemon.py          — start_daemon(), stop_daemon(), get_daemon_status()
chronicler/ui/__init__.py          — empty
chronicler/ui/server.py            — FastAPI app with all API routes
chronicler/ui/static/index.html    — single-page frontend (Alpine.js + Tailwind CDN)
tests/test_daemon.py               — tests for daemon helpers
tests/test_ui_server.py            — tests for FastAPI routes using TestClient

# Modified files
chronicler/storage/db.py           — add get_all_recent_entries()
chronicler/cli/main.py             — add `ui` command; update start/stop to use daemon.py
pyproject.toml                     — add fastapi, uvicorn; add httpx to dev deps
tests/test_db.py                   — add tests for get_all_recent_entries()
```

---

## Task 1: Add fastapi, uvicorn, httpx dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Edit pyproject.toml**

In `pyproject.toml`, add to `dependencies`:
```toml
dependencies = [
    "watchdog>=4.0",
    "litellm>=1.30",
    "typer>=0.12",
    "pydantic>=2.6",
    "toml>=0.10",
    "rich>=13.7",
    "fastapi>=0.110",
    "uvicorn>=0.27",
]
```

And add `httpx` to dev deps (required by FastAPI TestClient):
```toml
[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-mock>=3.12", "httpx>=0.27"]
```

- [ ] **Step 2: Install**

```bash
pip install -e ".[dev]" --break-system-packages
```

Expected: installs fastapi, uvicorn, httpx without errors.

- [ ] **Step 3: Verify**

```bash
python -c "import fastapi, uvicorn, httpx; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add fastapi, uvicorn, httpx dependencies"
```

---

## Task 2: Extract daemon helpers to `chronicler/core/daemon.py`

**Files:**
- Create: `chronicler/core/daemon.py` (`chronicler/core/__init__.py` already exists)
- Create: `tests/test_daemon.py`
- Modify: `chronicler/cli/main.py` (update `start` and `stop` commands)

Note: `--foreground` and `--path` flags already exist on the `start` command in `cli/main.py` — confirmed. The subprocess call `["chronicler", "start", "--foreground", "--path", str(project_path)]` is valid.

- [ ] **Step 1: Write failing tests**

Create `tests/test_daemon.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_daemon.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'chronicler.core.daemon'`

- [ ] **Step 3: Create `chronicler/core/daemon.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_daemon.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Update `chronicler/cli/main.py` to use daemon.py**

Replace the `_daemonize` function and the inline stop logic in `stop` command. At the top of `main.py`, add the import:

```python
from chronicler.core.daemon import start_daemon, stop_daemon, get_daemon_status
```

Replace the `_daemonize` function (lines 320–331) with:

```python
def _daemonize(project_path: Path, project, config, db) -> None:
    start_daemon(project_path)
    console.print(f"Daemon started. Run [bold]chronicler stop[/bold] to stop.")
```

Replace the body of the `stop` command (lines 144–157) with:

```python
def stop(path: str = typer.Option(".", help="Project path")):
    """Stop the daemon."""
    project_path = Path(path).resolve()
    status = get_daemon_status(project_path)
    if status == "stopped":
        console.print("No daemon running.")
        return
    pid_file = project_path / ".chronicler" / "chronicler.pid"
    pid = int(pid_file.read_text().strip())
    stop_daemon(project_path)
    console.print(f"Stopped daemon (PID {pid})")
```

- [ ] **Step 6: Run full test suite**

```bash
pytest -v
```

Expected: all existing tests + 6 new daemon tests PASS

- [ ] **Step 7: Commit**

```bash
git add chronicler/core/daemon.py tests/test_daemon.py chronicler/cli/main.py
git commit -m "refactor: extract daemon helpers to core/daemon.py"
```

---

## Task 3: Add `get_all_recent_entries()` to `db.py`

**Files:**
- Modify: `chronicler/storage/db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Add `make_entry` helper to `tests/conftest.py`**

`tests/conftest.py` uses `tmp_db` (not `db`) as the DB fixture name. Add this helper function at the bottom of `tests/conftest.py`:

```python
import uuid

def make_entry(project_id: str, session_id: str, change_type: str = "feature") -> LogEntry:
    return LogEntry(
        id=str(uuid.uuid4()),
        project_id=project_id,
        session_id=session_id,
        timestamp=datetime.utcnow(),
        file=FileInfo(
            path="/tmp/foo.py", relative_path="foo.py",
            extension=".py", language="python",
            is_new=False, is_deleted=False, is_renamed=False, renamed_from=None,
        ),
        change=ChangeInfo(
            type=change_type, subtype=None, confidence=0.9,
            summary="Test change", impact="low",
            lines_added=1, lines_removed=0,
            diff_snapshot="+x = 1",
            affected_functions=None, affected_components=None,
        ),
        llm=LLMInfo(model="test", tokens_used=10, prompt_version="1.0", processing_ms=100),
        context={}, tags=[], manually_edited=False, notes=None,
    )
```

Note: `context={}` (dict, not list) — matches the existing `sample_entry` fixture in conftest.

- [ ] **Step 2: Write failing tests**

Add to `tests/test_db.py`:

```python
def test_get_all_recent_entries_empty(tmp_db):
    results = tmp_db.get_all_recent_entries()
    assert results == []


def test_get_all_recent_entries_returns_dicts(tmp_db, sample_project, sample_session):
    from tests.conftest import make_entry
    tmp_db.insert_project(sample_project)
    tmp_db.insert_session(sample_session)
    tmp_db.insert_log_entry(make_entry(sample_project.id, sample_session.id, change_type="feature"))
    tmp_db.insert_log_entry(make_entry(sample_project.id, sample_session.id, change_type="bug_fix"))
    results = tmp_db.get_all_recent_entries(limit=10)
    assert len(results) == 2
    required = {"rowid", "id", "project_id", "project_name", "change_type",
                "change_summary", "file_relative_path", "change_impact",
                "timestamp", "session_id", "change_diff_snapshot"}
    for entry in results:
        assert required.issubset(entry.keys())


def test_get_all_recent_entries_filter_by_project(tmp_db, sample_project, sample_session):
    from tests.conftest import make_entry
    tmp_db.insert_project(sample_project)
    tmp_db.insert_session(sample_session)
    tmp_db.insert_log_entry(make_entry(sample_project.id, sample_session.id))
    results = tmp_db.get_all_recent_entries(project_id=sample_project.id)
    assert len(results) == 1
    assert tmp_db.get_all_recent_entries(project_id="nonexistent-id") == []


def test_get_all_recent_entries_filter_by_change_type(tmp_db, sample_project, sample_session):
    from tests.conftest import make_entry
    tmp_db.insert_project(sample_project)
    tmp_db.insert_session(sample_session)
    tmp_db.insert_log_entry(make_entry(sample_project.id, sample_session.id, change_type="feature"))
    tmp_db.insert_log_entry(make_entry(sample_project.id, sample_session.id, change_type="bug_fix"))
    results = tmp_db.get_all_recent_entries(change_type="feature")
    assert len(results) == 1
    assert results[0]["change_type"] == "feature"


def test_get_all_recent_entries_after_rowid(tmp_db, sample_project, sample_session):
    from tests.conftest import make_entry
    tmp_db.insert_project(sample_project)
    tmp_db.insert_session(sample_session)
    tmp_db.insert_log_entry(make_entry(sample_project.id, sample_session.id))
    tmp_db.insert_log_entry(make_entry(sample_project.id, sample_session.id))
    all_entries = tmp_db.get_all_recent_entries()
    assert len(all_entries) == 2
    min_rowid = min(e["rowid"] for e in all_entries)
    results = tmp_db.get_all_recent_entries(after_rowid=min_rowid)
    assert len(results) == 1
    assert results[0]["rowid"] > min_rowid
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_db.py -k "get_all_recent" -v
```

Expected: FAIL — `AttributeError: 'Database' object has no attribute 'get_all_recent_entries'`

- [ ] **Step 4: Commit conftest change before implementing**

```bash
git add tests/conftest.py
git commit -m "test: add make_entry helper to conftest"
```

- [ ] **Step 5: Add `get_all_recent_entries()` to `chronicler/storage/db.py`**

Add this method after `get_recent_entries` (around line 277):

```python
def get_all_recent_entries(
    self,
    limit: int = 50,
    project_id: str | None = None,
    change_type: str | None = None,
    after_rowid: int | None = None,
) -> list[dict]:
    """Fetch recent entries across all projects as plain dicts.
    Uses SQLite rowid (monotonic int) for SSE cursor support.
    """
    query = """
        SELECT le.rowid, le.id, le.project_id, p.name AS project_name,
               le.session_id, le.timestamp, le.file_relative_path,
               le.change_type, le.change_summary, le.change_impact,
               le.change_diff_snapshot
        FROM log_entries le
        JOIN projects p ON le.project_id = p.id
        WHERE 1=1
    """
    params: list = []
    if project_id is not None:
        query += " AND le.project_id = ?"
        params.append(project_id)
    if change_type is not None:
        query += " AND le.change_type = ?"
        params.append(change_type)
    if after_rowid is not None:
        query += " AND le.rowid > ?"
        params.append(after_rowid)
    query += " ORDER BY le.rowid DESC LIMIT ?"
    params.append(limit)

    rows = self._get_conn().execute(query, params).fetchall()
    return [
        {
            "rowid": row["rowid"],
            "id": row["id"],
            "project_id": row["project_id"],
            "project_name": row["project_name"],
            "session_id": row["session_id"],
            "timestamp": row["timestamp"],
            "file_relative_path": row["file_relative_path"],
            "change_type": row["change_type"],
            "change_summary": row["change_summary"],
            "change_impact": row["change_impact"],
            "change_diff_snapshot": row["change_diff_snapshot"],
        }
        for row in rows
    ]
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_db.py -v
```

Expected: all tests PASS (including new ones)

- [ ] **Step 7: Commit**

```bash
git add chronicler/storage/db.py tests/test_db.py
git commit -m "feat: add get_all_recent_entries() to Database for cross-project queries"
```

---

## Task 4: FastAPI server skeleton — GET /api/projects + serve index.html

**Files:**
- Create: `chronicler/ui/__init__.py`
- Create: `chronicler/ui/server.py`
- Create: `chronicler/ui/static/index.html` (placeholder)
- Create: `tests/test_ui_server.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ui_server.py`:

```python
import pytest
from fastapi.testclient import TestClient
from chronicler.ui.server import create_app
from chronicler.storage.db import Database


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = Database(db_path)
    db.initialize()
    app = create_app(db)
    return TestClient(app)


def test_get_projects_empty(client):
    response = client.get("/api/projects")
    assert response.status_code == 200
    assert response.json() == []


def test_get_projects_returns_status(tmp_path):
    from chronicler.storage.schema import Project
    from datetime import datetime
    import uuid
    db_path = str(tmp_path / "test.db")
    db = Database(db_path)
    db.initialize()
    project = Project(
        id=str(uuid.uuid4()), name="test-app", path=str(tmp_path / "test-app"),
        created_at=datetime.utcnow(), git_enabled=False, primary_language="python",
        languages=[], framework="python", description=None, log_mode="debounced",
        ignore_patterns=[], tags=[],
    )
    db.insert_project(project)
    app = create_app(db)
    c = TestClient(app)
    response = c.get("/api/projects")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "test-app"
    assert data[0]["status"] in ("running", "stopped")
    assert "id" in data[0]
    assert "path" in data[0]
    assert "framework" in data[0]


def test_root_serves_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ui_server.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'chronicler.ui'`

- [ ] **Step 3: Create `chronicler/ui/__init__.py`**

```python
```
(empty file)

- [ ] **Step 4: Create placeholder `chronicler/ui/static/index.html`**

```html
<!DOCTYPE html>
<html><head><title>Chronicler</title></head>
<body><h1>Chronicler UI</h1><p>Coming soon.</p></body>
</html>
```

- [ ] **Step 5: Create `chronicler/ui/server.py`**

```python
from __future__ import annotations
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from chronicler.storage.db import Database
from chronicler.core.daemon import get_daemon_status

STATIC_DIR = Path(__file__).parent / "static"


def _get_db() -> Database:
    db_path = Path.home() / ".config" / "chronicler" / "chronicler.db"
    db = Database(str(db_path))
    db.initialize()
    return db


def create_app(db: Database | None = None) -> FastAPI:
    if db is None:
        db = _get_db()

    app = FastAPI(title="Chronicler UI")

    @app.get("/api/projects")
    def list_projects():
        conn = db._get_conn()
        rows = conn.execute("SELECT * FROM projects ORDER BY name").fetchall()
        result = []
        for row in rows:
            project_path = Path(row["path"])
            result.append({
                "id": row["id"],
                "name": row["name"],
                "path": row["path"],
                "framework": row["framework"] or "",
                "log_mode": row["log_mode"],
                "status": get_daemon_status(project_path),
            })
        return JSONResponse(result)

    @app.get("/")
    def root():
        return FileResponse(str(STATIC_DIR / "index.html"))

    # Mount static files (CSS, JS if needed in future)
    if (STATIC_DIR).exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_ui_server.py -v
```

Expected: 3 tests PASS

- [ ] **Step 7: Commit**

```bash
git add chronicler/ui/__init__.py chronicler/ui/server.py chronicler/ui/static/index.html tests/test_ui_server.py
git commit -m "feat: add FastAPI server skeleton with GET /api/projects"
```

---

## Task 5: Project management routes — add, start, stop, detect-framework

**Files:**
- Modify: `chronicler/ui/server.py`
- Modify: `tests/test_ui_server.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_ui_server.py`:

```python
def test_detect_framework_nextjs(client, tmp_path):
    proj = tmp_path / "myapp"
    proj.mkdir()
    (proj / "next.config.js").touch()
    response = client.get(f"/api/detect-framework?path={proj}")
    assert response.status_code == 200
    assert response.json()["framework"] == "nextjs"


def test_detect_framework_unknown(client, tmp_path):
    proj = tmp_path / "emptyapp"
    proj.mkdir()
    response = client.get(f"/api/detect-framework?path={proj}")
    assert response.status_code == 200
    assert response.json()["framework"] == ""


def test_add_project(client, tmp_path):
    proj = tmp_path / "newapp"
    proj.mkdir()
    (proj / "next.config.js").touch()
    response = client.post("/api/projects", json={"path": str(proj), "name": "newapp"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "newapp"
    assert data["framework"] == "nextjs"
    assert "id" in data
    # .chronicler dir should be created
    assert (proj / ".chronicler").exists()
    assert (proj / ".chronicler" / "config.toml").exists()


def test_add_project_invalid_path(client, tmp_path):
    response = client.post("/api/projects", json={"path": "/does/not/exist", "name": "x"})
    assert response.status_code == 400


def test_start_stop_project(client, tmp_path):
    from unittest.mock import patch
    proj = tmp_path / "startapp"
    proj.mkdir()
    # Add project first
    client.post("/api/projects", json={"path": str(proj), "name": "startapp"})
    projects = client.get("/api/projects").json()
    project_id = next(p["id"] for p in projects if p["name"] == "startapp")

    with patch("chronicler.ui.server.start_daemon") as mock_start:
        response = client.post(f"/api/projects/{project_id}/start")
        assert response.status_code == 200
        mock_start.assert_called_once()

    with patch("chronicler.ui.server.stop_daemon") as mock_stop:
        response = client.post(f"/api/projects/{project_id}/stop")
        assert response.status_code == 200
        mock_stop.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ui_server.py -k "detect_framework or add_project or start_stop" -v
```

Expected: FAIL — routes don't exist yet

- [ ] **Step 3: Add routes to `chronicler/ui/server.py`**

Add these imports at the top of `server.py`:

```python
import uuid
import toml
from datetime import datetime
from fastapi import HTTPException
from pydantic import BaseModel
from chronicler.core.daemon import get_daemon_status, start_daemon, stop_daemon
from chronicler.storage.schema import Project
from chronicler.storage.map import MapManager
from chronicler.cli.main import _detect_framework
```

Add a request model:

```python
class AddProjectRequest(BaseModel):
    path: str
    name: str
```

Add these routes inside `create_app()`, after the `/api/projects` GET route:

```python
@app.get("/api/detect-framework")
def detect_framework(path: str):
    framework = _detect_framework(Path(path))
    return {"framework": framework or ""}

@app.post("/api/projects")
def add_project(req: AddProjectRequest):
    project_path = Path(req.path)
    if not project_path.exists() or not project_path.is_dir():
        raise HTTPException(status_code=400, detail="Path does not exist or is not a directory")

    framework = _detect_framework(project_path) or ""
    chronicler_dir = project_path / ".chronicler"
    chronicler_dir.mkdir(exist_ok=True)
    (chronicler_dir / "handoffs").mkdir(exist_ok=True)

    config_content = (
        f'[project]\nname = "{req.name}"\nframework = "{framework}"\nlanguages = []\n\n'
        f'[logging]\nmode = "debounced"\n\n[models]\ntier = "cloud"\n'
    )
    (chronicler_dir / "config.toml").write_text(config_content)

    MapManager(str(chronicler_dir)).create_initial(req.name, framework or None, [])

    project_id = str(uuid.uuid4())
    git_enabled = (project_path / ".git").exists()
    project = Project(
        id=project_id, name=req.name, path=str(project_path),
        created_at=datetime.utcnow(), git_enabled=git_enabled,
        primary_language="unknown", languages=[], framework=framework or None,
        description=None, log_mode="debounced", ignore_patterns=[], tags=[],
    )
    # Only insert if not already registered
    existing = db.get_project_by_path(str(project_path))
    if existing is None:
        db.insert_project(project)
        project_id = project.id
    else:
        project_id = existing.id

    # Add .chronicler/ to .gitignore if present
    gitignore = project_path / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text()
        if ".chronicler/" not in content:
            gitignore.write_text(content + "\n.chronicler/\n")

    return {"id": project_id, "name": req.name, "path": str(project_path), "framework": framework}

@app.post("/api/projects/{project_id}/start")
def start_project(project_id: str):
    project = db.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    start_daemon(Path(project.path))
    return {"status": "started"}

@app.post("/api/projects/{project_id}/stop")
def stop_project(project_id: str):
    project = db.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    stop_daemon(Path(project.path))
    return {"status": "stopped"}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_ui_server.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add chronicler/ui/server.py tests/test_ui_server.py
git commit -m "feat: add project management API routes (add, start, stop, detect-framework)"
```

---

## Task 6: Activity routes — GET /api/activity + SSE stream

**Files:**
- Modify: `chronicler/ui/server.py`
- Modify: `tests/test_ui_server.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_ui_server.py`:

```python
def test_get_activity_empty(client):
    response = client.get("/api/activity")
    assert response.status_code == 200
    assert response.json() == []


def test_get_activity_with_entries(tmp_path):
    import uuid
    from datetime import datetime
    from chronicler.storage.schema import Project, Session
    from chronicler.storage.db import Database

    db_path = str(tmp_path / "test.db")
    db = Database(db_path)
    db.initialize()

    proj_path = tmp_path / "myapp"
    proj_path.mkdir()
    project = Project(
        id=str(uuid.uuid4()), name="myapp", path=str(proj_path),
        created_at=datetime.utcnow(), git_enabled=False,
        primary_language="python", languages=[], framework=None,
        description=None, log_mode="debounced", ignore_patterns=[], tags=[],
    )
    db.insert_project(project)

    session = Session(
        id=str(uuid.uuid4()), project_id=project.id,
        started_at=datetime.utcnow(), ended_at=None, duration_minutes=None,
        entry_count=0, files_touched=[], primary_change_type=None,
        session_summary=None, session_health=None,
        key_decisions=[], open_threads=[], handoff_generated=False, tokens_used=0,
    )
    db.insert_session(session)

    from tests.conftest import make_entry
    db.insert_log_entry(make_entry(project.id, session.id, change_type="feature"))

    app = create_app(db)
    c = TestClient(app)
    response = c.get("/api/activity")
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 1
    assert entries[0]["change_type"] == "feature"
    assert entries[0]["project_name"] == "myapp"
    assert "rowid" in entries[0]


def test_get_activity_filter_by_change_type(tmp_path):
    import uuid
    from datetime import datetime
    from chronicler.storage.schema import Project, Session
    from chronicler.storage.db import Database
    from tests.conftest import make_entry

    db_path = str(tmp_path / "test2.db")
    db = Database(db_path)
    db.initialize()
    proj_path = tmp_path / "app2"
    proj_path.mkdir()
    project = Project(
        id=str(uuid.uuid4()), name="app2", path=str(proj_path),
        created_at=datetime.utcnow(), git_enabled=False, primary_language="python",
        languages=[], framework=None, description=None, log_mode="debounced",
        ignore_patterns=[], tags=[],
    )
    db.insert_project(project)
    session = Session(
        id=str(uuid.uuid4()), project_id=project.id, started_at=datetime.utcnow(),
        ended_at=None, duration_minutes=None, entry_count=0, files_touched=[],
        primary_change_type=None, session_summary=None, session_health=None,
        key_decisions=[], open_threads=[], handoff_generated=False, tokens_used=0,
    )
    db.insert_session(session)
    db.insert_log_entry(make_entry(project.id, session.id, change_type="feature"))
    db.insert_log_entry(make_entry(project.id, session.id, change_type="bug_fix"))

    app = create_app(db)
    c = TestClient(app)
    response = c.get("/api/activity?change_type=feature")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["change_type"] == "feature"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ui_server.py -k "activity" -v
```

Expected: FAIL — `/api/activity` route not found

- [ ] **Step 3: Add activity routes to `chronicler/ui/server.py`**

Add this import at the top:
```python
import asyncio
from fastapi.responses import StreamingResponse
```

Add these routes inside `create_app()`:

```python
@app.get("/api/activity")
def get_activity(
    project_id: str | None = None,
    change_type: str | None = None,
    limit: int = 50,
):
    entries = db.get_all_recent_entries(
        limit=limit,
        project_id=project_id,
        change_type=change_type,
    )
    return JSONResponse(entries)


@app.get("/api/activity/stream")
async def activity_stream(project_id: str | None = None):
    """SSE endpoint. Pushes new log_entries rows as they are inserted."""
    async def event_generator():
        # Get the current max rowid as starting cursor
        conn = db._get_conn()
        row = conn.execute("SELECT MAX(rowid) as max_rowid FROM log_entries").fetchone()
        last_rowid = row["max_rowid"] or 0

        while True:
            await asyncio.sleep(1)
            new_entries = db.get_all_recent_entries(
                limit=50,
                project_id=project_id,
                after_rowid=last_rowid,
            )
            if new_entries:
                # Entries come back newest-first; send oldest-first so feed builds naturally
                for entry in reversed(new_entries):
                    import json
                    yield f"data: {json.dumps(entry)}\n\n"
                    last_rowid = max(last_rowid, entry["rowid"])

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_ui_server.py -v
```

Expected: all tests PASS (SSE endpoint is not tested here — verified manually later)

- [ ] **Step 5: Commit**

```bash
git add chronicler/ui/server.py tests/test_ui_server.py
git commit -m "feat: add GET /api/activity and SSE /api/activity/stream routes"
```

---

## Task 7: Utility routes — handoff, map, groq-key, sessions

**Files:**
- Modify: `chronicler/ui/server.py`
- Modify: `tests/test_ui_server.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_ui_server.py`:

```python
def test_get_map_not_found(tmp_path):
    import uuid
    from datetime import datetime
    from chronicler.storage.schema import Project
    from chronicler.storage.db import Database
    db2 = Database(str(tmp_path / "db2.db"))
    db2.initialize()
    proj_path = tmp_path / "mapapp"
    proj_path.mkdir()
    project = Project(
        id=str(uuid.uuid4()), name="mapapp", path=str(proj_path),
        created_at=datetime.utcnow(), git_enabled=False, primary_language="python",
        languages=[], framework=None, description=None, log_mode="debounced",
        ignore_patterns=[], tags=[],
    )
    db2.insert_project(project)
    app = create_app(db2)
    c = TestClient(app)
    response = c.get(f"/api/projects/{project.id}/map")
    assert response.status_code == 404


def test_groq_key_status_detected(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-123")
    response = client.get("/api/config/groq-key-status")
    assert response.status_code == 200
    assert response.json()["detected"] is True


def test_groq_key_status_not_detected(client, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    response = client.get("/api/config/groq-key-status")
    assert response.status_code == 200
    assert response.json()["detected"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ui_server.py -k "map or groq" -v
```

Expected: FAIL — routes don't exist

- [ ] **Step 3: Add utility routes to `chronicler/ui/server.py`**

Add these imports:
```python
from chronicler.config.settings import load_config
from chronicler.storage.map import MapManager
from chronicler.llm.classifier import HandoffGenerator
```

Add these routes inside `create_app()`:

```python
@app.get("/api/projects/{project_id}/map")
def get_map(project_id: str):
    project = db.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    map_path = Path(project.path) / ".chronicler" / "CHRONICLER_MAP.md"
    if not map_path.exists():
        raise HTTPException(status_code=404, detail="Map not found — project may not have activity yet")
    return {"markdown": map_path.read_text()}


@app.post("/api/projects/{project_id}/handoff")
def generate_handoff(project_id: str):
    project = db.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project_path = Path(project.path)
    try:
        config = load_config(str(project_path))
        map_mgr = MapManager(str(project_path / ".chronicler"))
        output = HandoffGenerator(config).generate(project, map_mgr.read(), db, 5)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Handoff generation failed: {e}")

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    out_path = project_path / ".chronicler" / "handoffs" / f"{date_str}-handoff.md"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(output)
    return {"markdown": output, "saved_to": str(out_path)}


@app.get("/api/config/groq-key-status")
def groq_key_status():
    detected = bool(os.environ.get("GROQ_API_KEY"))
    return {"detected": detected}


class GroqKeyRequest(BaseModel):
    key: str


@app.post("/api/config/groq-key")
def set_groq_key(req: GroqKeyRequest):
    global_config_path = Path.home() / ".config" / "chronicler" / "config.toml"
    os.environ["GROQ_API_KEY"] = req.key
    if global_config_path.exists():
        config_data = toml.loads(global_config_path.read_text())
    else:
        config_data = {}
    if "groq" not in config_data:
        config_data["groq"] = {}
    config_data["groq"]["api_key"] = req.key
    global_config_path.write_text(toml.dumps(config_data))
    return {"ok": True}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_ui_server.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add chronicler/ui/server.py tests/test_ui_server.py
git commit -m "feat: add handoff, map, groq-key, and detect-framework utility routes"
```

---

## Task 8: `chronicler ui` CLI command

**Files:**
- Modify: `chronicler/cli/main.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_ui_server.py`:

```python
def test_ui_app_is_importable():
    """Smoke test: create_app() returns a FastAPI instance without error."""
    from chronicler.ui.server import create_app
    from fastapi import FastAPI
    app = create_app()
    assert isinstance(app, FastAPI)
```

- [ ] **Step 2: Run test to verify it passes already**

```bash
pytest tests/test_ui_server.py::test_ui_app_is_importable -v
```

Expected: PASS (already works from Task 4)

- [ ] **Step 3: Add `ui` command to `chronicler/cli/main.py`**

Add this import at the top of `main.py`:
```python
import webbrowser
```

Add this command after the existing `map` command (before `if __name__ == "__main__":`):

```python
@app.command()
def ui(
    port: int = typer.Option(8765, help="Port to serve the UI on"),
    no_open: bool = typer.Option(False, "--no-open", help="Don't open browser automatically"),
):
    """Launch the Chronicler web dashboard."""
    import socket
    # Check if port is available
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("localhost", port)) == 0:
            console.print(f"[red]Port {port} is already in use.[/red]")
            console.print(f"Try: [bold]chronicler ui --port {port + 1}[/bold]")
            raise typer.Exit(1)

    import uvicorn
    from chronicler.ui.server import create_app

    url = f"http://localhost:{port}"
    console.print(f"[bold]Chronicler UI[/bold] → {url}")
    console.print("Press [bold]Ctrl+C[/bold] to stop.\n")

    if not no_open:
        webbrowser.open(url)

    app_instance = create_app()
    uvicorn.run(app_instance, host="127.0.0.1", port=port, log_level="warning")
```

- [ ] **Step 4: Verify the command is registered**

```bash
chronicler --help
```

Expected: `ui` appears in the command list

- [ ] **Step 5: Smoke test — start and immediately stop**

```bash
timeout 3 chronicler ui --no-open --port 8766 || true
```

Expected: prints the URL line, then exits (timeout kills it — that's expected)

- [ ] **Step 6: Run full test suite**

```bash
pytest -v
```

Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add chronicler/cli/main.py
git commit -m "feat: add 'chronicler ui' command to launch web dashboard"
```

---

## Task 9: Frontend — dashboard shell (layout, topbar, project cards)

**Files:**
- Modify: `chronicler/ui/static/index.html`

Note: The frontend is a single HTML file with no build step. These tasks replace the placeholder progressively. Testing is visual — run `chronicler ui` and verify in the browser.

- [ ] **Step 1: Start the server for visual testing**

```bash
chronicler ui --port 8765
```

Open http://localhost:8765 in your browser. Keep this running as you work.

- [ ] **Step 2: Replace `index.html` with the dashboard shell**

Write the following to `chronicler/ui/static/index.html` (this is the complete file for this task — the activity feed and log tab content will be added in later tasks):

```html
<!DOCTYPE html>
<html lang="en" x-data="chroniclerApp()" x-init="init()">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chronicler</title>
<script src="https://cdn.tailwindcss.com"></script>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
<style>
  [x-cloak] { display: none !important; }
  body { background: #0d1117; color: #e6edf3; }
  .traffic-light { width: 10px; height: 10px; border-radius: 50%; cursor: pointer; flex-shrink: 0; transition: transform 0.15s; }
  .traffic-light:hover { transform: scale(1.4); }
  .running { background: #3fb950; box-shadow: 0 0 6px #3fb95066; }
  .stopped { background: #6b7280; }
  .pulse { animation: pulse 2s infinite; }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
  ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-thumb { background: #374151; border-radius: 2px; }
</style>
</head>
<body class="flex flex-col h-screen overflow-hidden" x-cloak>

<!-- Top bar -->
<header class="flex items-center gap-3 px-5 h-13 border-b border-gray-800 bg-gray-900 flex-shrink-0" style="height:52px">
  <div class="flex items-center gap-2">
    <div class="w-6 h-6 rounded-md flex items-center justify-center text-xs font-bold text-white" style="background:linear-gradient(135deg,#3fb950,#1f6feb)">C</div>
    <span class="font-semibold text-sm">Chronicler</span>
    <span class="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">v0.1.0</span>
  </div>
  <div class="flex-1"></div>
  <!-- Live indicator -->
  <div class="flex items-center gap-1.5 text-xs text-green-400">
    <div class="w-1.5 h-1.5 rounded-full bg-green-400 pulse"></div>
    Live
  </div>
  <!-- Rotating hint -->
  <div class="text-xs text-gray-500 bg-gray-800 border border-gray-700 px-3 py-1 rounded-md hidden md:block" x-text="currentHint"></div>
</header>

<!-- Main layout -->
<div class="flex flex-1 overflow-hidden">

  <!-- Left: Projects panel -->
  <aside class="w-64 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col overflow-hidden">
    <div class="flex items-center justify-between px-4 py-3 border-b border-gray-800">
      <span class="text-xs font-semibold uppercase tracking-wider text-gray-500">Projects</span>
      <button @click="showAddProject = true"
              class="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 bg-blue-900/20 border border-blue-900/40 px-2 py-1 rounded-md transition-colors"
              title="Watch a new project folder">
        ＋ Add project
      </button>
    </div>

    <!-- Project list -->
    <div class="flex-1 overflow-y-auto p-3 space-y-2">
      <template x-if="projects.length === 0">
        <div class="text-xs text-gray-500 text-center py-8 px-4">
          No projects yet.<br>
          <button @click="showAddProject = true" class="text-blue-400 hover:underline mt-1">Add your first project →</button>
        </div>
      </template>
      <template x-for="project in projects" :key="project.id">
        <div class="bg-gray-800 rounded-lg p-3 border border-gray-700 hover:border-gray-600 transition-colors cursor-pointer"
             :class="selectedProjectId === project.id ? 'border-green-900/50 bg-green-950/20' : ''"
             @click="selectedProjectId = project.id; activeTab = 'activity'">
          <div class="flex items-center gap-2 mb-2">
            <!-- Traffic light -->
            <div class="traffic-light"
                 :class="project.status === 'running' ? 'running' : 'stopped'"
                 :title="project.status === 'running' ? 'Watching — click to stop' : 'Not watching — click to start'"
                 @click.stop="toggleDaemon(project)">
            </div>
            <span class="font-semibold text-sm flex-1 truncate" x-text="project.name"></span>
            <span x-show="project.framework" x-text="project.framework"
                  class="text-xs text-gray-500 bg-gray-700 px-1.5 py-0.5 rounded"></span>
          </div>
          <div class="flex gap-4 mb-2">
            <div>
              <div class="text-sm font-semibold" :class="project.status === 'running' ? 'text-green-400' : 'text-gray-400'" x-text="(projectChangesToday[project.id] || 0)"></div>
              <div class="text-xs text-gray-500">changes today</div>
            </div>
          </div>
          <div class="flex gap-2">
            <button @click.stop="viewMap(project)"
                    class="flex-1 text-xs py-1 rounded bg-gray-700 hover:bg-gray-600 text-gray-400 hover:text-gray-200 transition-colors"
                    title="View the auto-generated overview of this project">
              View map
            </button>
            <button @click.stop="generateHandoff(project)"
                    class="flex-1 text-xs py-1 rounded bg-blue-900/20 border border-blue-900/40 hover:bg-blue-900/40 text-blue-400 transition-colors"
                    title="Generate a briefing so your AI agent can pick up where you left off">
              ✦ Handoff
            </button>
          </div>
        </div>
      </template>
    </div>
  </aside>

  <!-- Right: Activity + Log panel -->
  <main class="flex-1 flex flex-col overflow-hidden">
    <!-- Tab bar -->
    <div class="flex items-center gap-0 px-5 border-b border-gray-800 bg-gray-900" style="height:44px">
      <button @click="activeTab = 'activity'"
              class="px-4 h-full text-xs font-medium border-b-2 transition-colors"
              :class="activeTab === 'activity' ? 'text-blue-400 border-blue-400' : 'text-gray-500 border-transparent hover:text-gray-300'">
        Activity
      </button>
      <button @click="activeTab = 'log'"
              class="px-4 h-full text-xs font-medium border-b-2 transition-colors"
              :class="activeTab === 'log' ? 'text-blue-400 border-blue-400' : 'text-gray-500 border-transparent hover:text-gray-300'">
        Full Log
      </button>
      <div class="flex-1"></div>
      <button @click="generateHandoffAll()"
              class="flex items-center gap-1.5 text-xs font-semibold text-white px-3 py-1.5 rounded-md transition-opacity hover:opacity-80"
              style="background:linear-gradient(135deg,#1f6feb,#3fb950)"
              title="Generate a briefing document for all running projects — paste to your AI agent">
        ✦ Generate Handoff
      </button>
    </div>

    <!-- Tab content: Activity (placeholder — filled in Task 10) -->
    <div x-show="activeTab === 'activity'" class="flex-1 overflow-y-auto p-4">
      <p class="text-gray-500 text-sm">Activity feed — coming in next task</p>
    </div>

    <!-- Tab content: Full Log (placeholder — filled in Task 11) -->
    <div x-show="activeTab === 'log'" class="flex-1 overflow-y-auto p-4">
      <p class="text-gray-500 text-sm">Full log — coming in next task</p>
    </div>
  </main>
</div>

<!-- Add Project Modal (placeholder — full form in Task 13) -->
<div x-show="showAddProject" x-cloak class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="showAddProject = false">
  <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-96 shadow-2xl">
    <h3 class="font-semibold mb-4">Add Project</h3>
    <input x-model="newProjectPath" placeholder="/path/to/your/project" class="w-full bg-gray-800 border border-gray-700 rounded-md px-3 py-2 text-sm mb-2 focus:outline-none focus:border-blue-500">
    <input x-model="newProjectName" placeholder="Project name" class="w-full bg-gray-800 border border-gray-700 rounded-md px-3 py-2 text-sm mb-4 focus:outline-none focus:border-blue-500">
    <div class="flex gap-2 justify-end">
      <button @click="showAddProject = false" class="px-4 py-2 text-sm rounded-md bg-gray-800 text-gray-400 hover:text-white">Cancel</button>
      <button @click="addProject()" class="px-4 py-2 text-sm rounded-md font-semibold text-white" style="background:linear-gradient(135deg,#1f6feb,#3fb950)">Add</button>
    </div>
  </div>
</div>

<!-- Handoff modal -->
<div x-show="handoffResult" x-cloak class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="handoffResult = null">
  <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-2xl max-w-2xl max-h-96 flex flex-col shadow-2xl" style="width:600px">
    <div class="flex items-center justify-between mb-4">
      <h3 class="font-semibold">Handoff Document</h3>
      <button @click="handoffResult = null" class="text-gray-500 hover:text-gray-300 text-lg">×</button>
    </div>
    <pre class="flex-1 overflow-y-auto text-xs text-gray-300 bg-gray-800 rounded-md p-4 whitespace-pre-wrap" x-text="handoffResult"></pre>
    <button @click="navigator.clipboard.writeText(handoffResult); alert('Copied!')" class="mt-3 text-xs text-blue-400 hover:underline self-start">Copy to clipboard</button>
  </div>
</div>

<!-- Map modal -->
<div x-show="mapResult" x-cloak class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="mapResult = null">
  <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 shadow-2xl flex flex-col" style="width:600px;max-height:80vh">
    <div class="flex items-center justify-between mb-4">
      <h3 class="font-semibold">Project Map</h3>
      <button @click="mapResult = null" class="text-gray-500 hover:text-gray-300 text-lg">×</button>
    </div>
    <pre class="flex-1 overflow-y-auto text-xs text-gray-300 bg-gray-800 rounded-md p-4 whitespace-pre-wrap" x-text="mapResult"></pre>
  </div>
</div>

<script>
function chroniclerApp() {
  return {
    projects: [],
    projectChangesToday: {},
    selectedProjectId: null,
    activeTab: 'activity',
    showAddProject: false,
    newProjectPath: '',
    newProjectName: '',
    handoffResult: null,
    mapResult: null,
    activityEntries: [],
    logEntries: [],
    logSearch: '',
    logChangeType: '',
    activeChangeTypeFilter: '',
    hints: [
      'Click the coloured dot to start or stop watching a project',
      'Use ✦ Generate Handoff before handing off to an AI assistant',
      'The Full Log tab shows every change grouped by session',
    ],
    currentHint: '',
    hintIndex: 0,

    async init() {
      this.currentHint = this.hints[0];
      setInterval(() => {
        this.hintIndex = (this.hintIndex + 1) % this.hints.length;
        this.currentHint = this.hints[this.hintIndex];
      }, 8000);
      await this.loadProjects();
      setInterval(() => this.loadProjects(), 5000);
    },

    async loadProjects() {
      const res = await fetch('/api/projects');
      this.projects = await res.json();
    },

    async toggleDaemon(project) {
      const action = project.status === 'running' ? 'stop' : 'start';
      await fetch(`/api/projects/${project.id}/${action}`, { method: 'POST' });
      await this.loadProjects();
    },

    async addProject() {
      const name = this.newProjectName || this.newProjectPath.split('/').pop();
      await fetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: this.newProjectPath, name }),
      });
      this.newProjectPath = '';
      this.newProjectName = '';
      this.showAddProject = false;
      await this.loadProjects();
    },

    async generateHandoff(project) {
      const res = await fetch(`/api/projects/${project.id}/handoff`, { method: 'POST' });
      const data = await res.json();
      this.handoffResult = data.markdown || data.detail;
    },

    async generateHandoffAll() {
      const running = this.projects.filter(p => p.status === 'running');
      if (running.length === 0) {
        alert('No running projects to generate a handoff for.');
        return;
      }
      // Generate for the first running project; could be extended to all
      await this.generateHandoff(running[0]);
    },

    async viewMap(project) {
      const res = await fetch(`/api/projects/${project.id}/map`);
      if (res.ok) {
        const data = await res.json();
        this.mapResult = data.markdown;
      } else {
        this.mapResult = 'No map available yet — start watching and make some changes first.';
      }
    },
  };
}
</script>
</body>
</html>
```

- [ ] **Step 3: Reload browser and verify**

Hard-reload http://localhost:8765 (Cmd+Shift+R). Verify:
- Top bar shows "Chronicler", version badge, "Live" pulse, rotating hint
- Left panel shows projects from the DB (Macro, etc.) with traffic lights
- Tabs "Activity" and "Full Log" are present
- Clicking a traffic light calls start/stop (check Network tab in devtools)
- "✦ Generate Handoff" button is visible top right

- [ ] **Step 4: Commit**

```bash
git add chronicler/ui/static/index.html
git commit -m "feat: add dashboard shell with project cards and traffic lights"
```

---

## Task 10: Frontend — activity feed tab + filter pills

**Files:**
- Modify: `chronicler/ui/static/index.html`

- [ ] **Step 1: Replace the activity tab placeholder in `index.html`**

Find this block:
```html
<!-- Tab content: Activity (placeholder — filled in Task 10) -->
<div x-show="activeTab === 'activity'" class="flex-1 overflow-y-auto p-4">
  <p class="text-gray-500 text-sm">Activity feed — coming in next task</p>
</div>
```

Replace with:
```html
<!-- Tab content: Activity -->
<div x-show="activeTab === 'activity'" class="flex flex-col flex-1 overflow-hidden">
  <!-- Filter pills -->
  <div class="flex items-center gap-2 px-5 py-2 border-b border-gray-800 flex-wrap">
    <template x-for="ct in ['', 'feature', 'bug_fix', 'refactor', 'config', 'dependency', 'style', 'test', 'docs', 'delete', 'experiment']" :key="ct">
      <button @click="activeChangeTypeFilter = ct; loadActivity()"
              class="px-2.5 py-0.5 rounded-full text-xs border transition-colors"
              :class="activeChangeTypeFilter === ct
                ? 'bg-blue-900/30 border-blue-700 text-blue-400'
                : 'border-gray-700 text-gray-500 hover:text-gray-300 hover:border-gray-600'"
              x-text="ct === '' ? 'All' : ct.replace('_', ' ')">
      </button>
    </template>
  </div>
  <!-- Feed -->
  <div class="flex-1 overflow-y-auto px-5 py-4 space-y-2">
    <template x-if="activityEntries.length === 0">
      <div class="text-center py-16 text-gray-500 text-sm">
        <div class="text-2xl mb-3">📭</div>
        No changes logged yet.<br>
        <span class="text-xs mt-1 block">Start coding and Chronicler will pick them up automatically.</span>
      </div>
    </template>
    <template x-for="entry in activityEntries" :key="entry.rowid">
      <div class="flex items-start gap-3 px-3 py-2.5 rounded-md bg-gray-900 border border-transparent hover:border-gray-800 transition-colors"
           :class="entry._new ? 'border-green-900/30 bg-green-950/10' : ''">
        <!-- Project initial dot -->
        <div class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5"
             :style="`background:${projectColor(entry.project_id)}22; color:${projectColor(entry.project_id)}`"
             x-text="entry.project_name.charAt(0).toUpperCase()">
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-0.5">
            <span class="text-xs px-1.5 py-0.5 rounded-sm font-medium" :class="badgeClass(entry.change_type)" x-text="entry.change_type.replace('_', ' ')"></span>
            <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :class="impactClass(entry.change_impact)" :title="`${entry.change_impact} impact`"></span>
            <span class="text-xs text-gray-500 ml-auto flex-shrink-0" x-text="relativeTime(entry.timestamp)"></span>
          </div>
          <div class="text-xs text-gray-500 font-mono truncate" x-text="entry.file_relative_path"></div>
          <div class="text-xs text-gray-200 mt-0.5" x-text="entry.change_summary"></div>
        </div>
      </div>
    </template>
  </div>
</div>
```

- [ ] **Step 2: Add activity methods to the Alpine.js app object**

Inside the `chroniclerApp()` return object, add these methods and update `init()`:

Add to `init()` after `setInterval(() => this.loadProjects(), 5000);`:
```javascript
await this.loadActivity();
await this.loadChangesToday();
```

Add these methods:

```javascript
async loadActivity() {
  let url = '/api/activity?limit=50';
  if (this.activeChangeTypeFilter) url += `&change_type=${this.activeChangeTypeFilter}`;
  if (this.selectedProjectId) url += `&project_id=${this.selectedProjectId}`;
  const res = await fetch(url);
  this.activityEntries = await res.json();
},

async loadChangesToday() {
  const today = new Date().toISOString().slice(0, 10);
  for (const project of this.projects) {
    const res = await fetch(`/api/activity?project_id=${project.id}&limit=200`);
    const entries = await res.json();
    this.projectChangesToday[project.id] = entries.filter(e => e.timestamp.startsWith(today)).length;
  }
},

projectColor(projectId) {
  const colors = ['#3fb950', '#58a6ff', '#e3b341', '#f85149', '#d2a8ff', '#79c0ff'];
  const idx = this.projects.findIndex(p => p.id === projectId);
  return colors[idx % colors.length] || '#8b949e';
},

badgeClass(type) {
  const map = {
    feature: 'bg-blue-900/30 text-blue-400',
    bug_fix: 'bg-red-900/30 text-red-400',
    refactor: 'bg-yellow-900/30 text-yellow-400',
    config: 'bg-purple-900/30 text-purple-400',
    dependency: 'bg-gray-700 text-gray-400',
    style: 'bg-green-900/30 text-green-400',
    test: 'bg-orange-900/30 text-orange-400',
    docs: 'bg-teal-900/30 text-teal-400',
    delete: 'bg-red-900/40 text-red-500',
    experiment: 'bg-indigo-900/30 text-indigo-400',
  };
  return map[type] || 'bg-gray-700 text-gray-400';
},

impactClass(impact) {
  return { high: 'bg-red-500', medium: 'bg-yellow-400', low: 'bg-gray-500' }[impact] || 'bg-gray-500';
},

relativeTime(ts) {
  const diff = (Date.now() - new Date(ts + 'Z').getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return new Date(ts).toLocaleDateString();
},
```

- [ ] **Step 3: Reload browser and verify**

Hard-reload http://localhost:8765. Verify:
- Activity tab shows entries from the DB (if Macro is watched, you should see changes)
- Filter pills work — clicking "feature" filters the list
- Project initial dots appear with different colours per project
- Relative timestamps update
- Empty state shows when no entries

- [ ] **Step 4: Commit**

```bash
git add chronicler/ui/static/index.html
git commit -m "feat: add activity feed tab with filter pills and project colour coding"
```

---

## Task 11: Frontend — full log tab (search, session groups, expandable diffs)

Note: Session health labels (`productive` / `debugging` etc.) are stored in the `sessions` table, which `get_all_recent_entries()` does not join. Session headers will show the date range only, not health labels. Health labels are **out of scope for v1**.

**Files:**
- Modify: `chronicler/ui/static/index.html`

- [ ] **Step 1: Add `logEntries`, `logSessions` loading to the app**

Add to `init()` after `loadActivity()`:
```javascript
await this.loadLog();
```

Add to the `chroniclerApp()` methods:
```javascript
logSessions: [],
logProjectFilter: '',
expandedDiffs: {},

async loadLog() {
  let url = `/api/activity?limit=200`;
  if (this.logChangeType) url += `&change_type=${this.logChangeType}`;
  if (this.logProjectFilter) url += `&project_id=${this.logProjectFilter}`;
  const res = await fetch(url);
  const entries = await res.json();
  // Group by session_id, preserving order
  const sessionMap = {};
  const sessionOrder = [];
  for (const entry of entries) {
    if (!sessionMap[entry.session_id]) {
      sessionMap[entry.session_id] = [];
      sessionOrder.push(entry.session_id);
    }
    sessionMap[entry.session_id].push(entry);
  }
  this.logSessions = sessionOrder.map(sid => ({ session_id: sid, entries: sessionMap[sid] }));
},

toggleDiff(rowid) {
  this.expandedDiffs[rowid] = !this.expandedDiffs[rowid];
},
```

- [ ] **Step 2: Replace the full log tab placeholder**

Find:
```html
<!-- Tab content: Full Log (placeholder — filled in Task 11) -->
<div x-show="activeTab === 'log'" class="flex-1 overflow-y-auto p-4">
  <p class="text-gray-500 text-sm">Full log — coming in next task</p>
</div>
```

Replace with:
```html
<!-- Tab content: Full Log -->
<div x-show="activeTab === 'log'" class="flex flex-col flex-1 overflow-hidden">
  <!-- Controls -->
  <div class="flex items-center gap-2 px-5 py-2 border-b border-gray-800">
    <input x-model="logSearch" placeholder="Search changes..." class="flex-1 bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-xs focus:outline-none focus:border-blue-500">
    <select x-model="logChangeType" @change="loadLog()" class="bg-gray-800 border border-gray-700 rounded-md px-2 py-1.5 text-xs text-gray-400 focus:outline-none">
      <option value="">All types</option>
      <template x-for="ct in ['feature','bug_fix','refactor','config','dependency','style','test','docs','delete','experiment']" :key="ct">
        <option :value="ct" x-text="ct.replace('_',' ')"></option>
      </template>
    </select>
    <select x-model="logProjectFilter" @change="loadLog()" class="bg-gray-800 border border-gray-700 rounded-md px-2 py-1.5 text-xs text-gray-400 focus:outline-none">
      <option value="">All projects</option>
      <template x-for="p in projects" :key="p.id">
        <option :value="p.id" x-text="p.name"></option>
      </template>
    </select>
  </div>
  <!-- Session-grouped entries -->
  <div class="flex-1 overflow-y-auto px-5 py-4 space-y-6">
    <template x-if="logSessions.length === 0">
      <div class="text-center py-16 text-gray-500 text-sm">No entries found.</div>
    </template>
    <template x-for="(session, si) in logSessions" :key="session.session_id">
      <div>
        <div class="text-xs text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-2">
          <div class="flex-1 h-px bg-gray-800"></div>
          Session · <span x-text="session.entries[session.entries.length-1]?.timestamp?.slice(0,16).replace('T',' ')"></span>
          <div class="flex-1 h-px bg-gray-800"></div>
        </div>
        <div class="space-y-1.5">
          <template x-for="entry in session.entries.filter(e => !logSearch || e.change_summary.toLowerCase().includes(logSearch.toLowerCase()) || e.file_relative_path.toLowerCase().includes(logSearch.toLowerCase()))" :key="entry.rowid">
            <div class="bg-gray-900 rounded-md border border-gray-800 overflow-hidden">
              <!-- Entry header (always visible) -->
              <div class="flex items-start gap-3 px-3 py-2 cursor-pointer hover:bg-gray-800/50 transition-colors"
                   @click="toggleDiff(entry.rowid)">
                <div class="flex items-center gap-2 flex-1 min-w-0">
                  <span class="text-xs px-1.5 py-0.5 rounded-sm font-medium" :class="badgeClass(entry.change_type)" x-text="entry.change_type.replace('_', ' ')"></span>
                  <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :class="impactClass(entry.change_impact)"></span>
                  <span class="text-xs text-gray-500 font-mono truncate" x-text="entry.file_relative_path"></span>
                </div>
                <div class="flex items-center gap-3 flex-shrink-0">
                  <span class="text-xs text-gray-500" x-text="entry.timestamp?.slice(0,19).replace('T', ' ')"></span>
                  <span class="text-xs text-gray-600" x-text="expandedDiffs[entry.rowid] ? '▾' : '▸'"></span>
                </div>
              </div>
              <!-- Summary -->
              <div class="px-3 pb-2 text-xs text-gray-300" x-text="entry.change_summary"></div>
              <!-- Expandable diff -->
              <div x-show="expandedDiffs[entry.rowid]" x-cloak
                   class="border-t border-gray-800 px-3 py-2">
                <pre class="text-xs font-mono text-gray-400 whitespace-pre-wrap overflow-x-auto"
                     x-text="entry.change_diff_snapshot || 'No diff available'"></pre>
              </div>
            </div>
          </template>
        </div>
      </div>
    </template>
  </div>
</div>
```

- [ ] **Step 3: Reload and verify**

Reload http://localhost:8765. Click "Full Log" tab. Verify:
- Entries are grouped by session with a divider header
- Search box filters by file path and summary
- Type dropdown filters by change type
- Click an entry to expand/collapse the diff
- Project filter dropdown works

- [ ] **Step 4: Commit**

```bash
git add chronicler/ui/static/index.html
git commit -m "feat: add full log tab with session grouping, search, and expandable diffs"
```

---

## Task 12: Frontend — SSE live feed wiring

**Files:**
- Modify: `chronicler/ui/static/index.html`

- [ ] **Step 1: Add SSE connection to `init()`**

In the `init()` method, after the existing `setInterval` calls, add:

```javascript
this.connectSSE();
```

- [ ] **Step 2: Add `connectSSE()` method**

```javascript
connectSSE() {
  const source = new EventSource('/api/activity/stream');
  source.onmessage = (event) => {
    const entry = JSON.parse(event.data);
    entry._new = true;
    this.activityEntries.unshift(entry);
    // Keep list from growing unbounded
    if (this.activityEntries.length > 100) this.activityEntries.pop();
    // Update changes-today count
    const today = new Date().toISOString().slice(0, 10);
    if (entry.timestamp.startsWith(today)) {
      this.projectChangesToday[entry.project_id] = (this.projectChangesToday[entry.project_id] || 0) + 1;
    }
    // Clear the "new" highlight after 3 seconds
    setTimeout(() => { entry._new = false; }, 3000);
  };
  source.onerror = () => {
    // Reconnect after 5 seconds on error
    setTimeout(() => this.connectSSE(), 5000);
  };
},
```

- [ ] **Step 3: Verify live updates**

With the server running and Macro being watched:
1. Open http://localhost:8765 in the browser, Activity tab visible
2. Open any file in the Macro project and save it
3. Within a few seconds (after debounce + LLM classification), a new entry should appear at the top of the feed with a green highlight

- [ ] **Step 4: Commit**

```bash
git add chronicler/ui/static/index.html
git commit -m "feat: wire SSE live feed — activity updates instantly on file save"
```

---

## Task 13: Frontend — onboarding modal + contextual help

**Files:**
- Modify: `chronicler/ui/static/index.html`

- [ ] **Step 1: Add onboarding state to the app**

Add to the `chroniclerApp()` return object:
```javascript
showOnboarding: false,
onboardingStep: 1,
onboardingPath: '',
onboardingName: '',
onboardingFramework: '',
onboardingKeyDetected: false,
onboardingKey: '',
```

Add to `init()` — check if onboarding should be shown:
```javascript
// Show onboarding if no projects exist
if (this.projects.length === 0) {
  this.showOnboarding = true;
  this.checkGroqKey();
}
```

Add methods:
```javascript
async checkGroqKey() {
  const res = await fetch('/api/config/groq-key-status');
  const data = await res.json();
  this.onboardingKeyDetected = data.detected;
  if (this.onboardingKeyDetected && this.onboardingStep === 3) {
    setTimeout(() => { this.onboardingStep = 4; }, 1200);
  }
},

async detectFramework() {
  if (!this.onboardingPath) return;
  if (!this.onboardingName) {
    this.onboardingName = this.onboardingPath.split('/').pop();
  }
  const res = await fetch(`/api/detect-framework?path=${encodeURIComponent(this.onboardingPath)}`);
  const data = await res.json();
  this.onboardingFramework = data.framework;
},

async completeOnboarding() {
  if (this.onboardingPath) {
    const name = this.onboardingName || this.onboardingPath.split('/').pop();
    await fetch('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: this.onboardingPath, name }),
    });
    await this.loadProjects();
  }
  if (this.onboardingKey) {
    await fetch('/api/config/groq-key', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: this.onboardingKey }),
    });
  }
  this.showOnboarding = false;
},
```

- [ ] **Step 2: Add the onboarding modal to `index.html`**

Add before the closing `</body>` tag (after the existing modals):

```html
<!-- Onboarding modal -->
<div x-show="showOnboarding" x-cloak class="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
  <div class="bg-gray-900 border border-gray-700 rounded-2xl overflow-hidden shadow-2xl" style="width:500px">

    <!-- Step progress bar -->
    <div class="flex gap-1.5 px-6 pt-5">
      <template x-for="s in [1,2,3,4]" :key="s">
        <div class="h-1 flex-1 rounded-full transition-colors duration-300"
             :class="s < onboardingStep ? 'bg-green-400' : s === onboardingStep ? 'bg-blue-400' : 'bg-gray-700'">
        </div>
      </template>
    </div>

    <!-- Step 1: Welcome -->
    <div x-show="onboardingStep === 1" class="px-6 py-6">
      <div class="w-12 h-12 rounded-xl bg-green-900/30 flex items-center justify-center text-2xl mb-4">📖</div>
      <h2 class="text-lg font-bold mb-2">Welcome to Chronicler</h2>
      <p class="text-sm text-gray-400 leading-relaxed mb-4">
        Chronicler watches your project folders while you code and <strong class="text-gray-200">automatically logs every change</strong> — what you built, what you fixed, and what's still in progress.
      </p>
      <p class="text-sm text-gray-400 leading-relaxed mb-6">
        When you hand off to an AI coding assistant, it starts completely blind. Chronicler fixes that — one click generates a full briefing so your agent knows exactly where to pick up.
      </p>
      <div class="bg-blue-900/20 border border-blue-900/40 rounded-lg px-4 py-3 text-xs text-gray-400 mb-6">
        💡 <strong class="text-blue-300">No coding experience needed.</strong> Once it's running, Chronicler works silently in the background.
      </div>
      <div class="flex justify-end">
        <button @click="onboardingStep = 2" class="px-5 py-2 rounded-lg text-sm font-semibold text-white" style="background:linear-gradient(135deg,#1f6feb,#3fb950)">Get started →</button>
      </div>
    </div>

    <!-- Step 2: Add project -->
    <div x-show="onboardingStep === 2" class="px-6 py-6">
      <div class="w-12 h-12 rounded-xl bg-blue-900/30 flex items-center justify-center text-2xl mb-4">📁</div>
      <h2 class="text-lg font-bold mb-2">Add your first project</h2>
      <p class="text-sm text-gray-400 mb-5">Point Chronicler at a folder on your computer. It'll start watching for changes as you code.</p>
      <div class="mb-3">
        <label class="text-xs font-semibold text-gray-500 uppercase tracking-wider block mb-1.5">
          Project folder <span class="font-normal text-gray-600 normal-case">— where your code lives</span>
        </label>
        <input x-model="onboardingPath" @blur="detectFramework()"
               placeholder="/Users/you/projects/my-app"
               class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
               title="Paste the full path to your project folder (e.g. /Users/yourname/projects/myapp)">
        <div x-show="onboardingFramework" class="mt-1.5 inline-flex items-center gap-1.5 text-xs text-green-400 bg-green-900/20 border border-green-900/40 px-2.5 py-1 rounded-full">
          ✓ <span x-text="onboardingFramework"></span> detected
        </div>
      </div>
      <div class="mb-5">
        <label class="text-xs font-semibold text-gray-500 uppercase tracking-wider block mb-1.5">
          Project name <span class="font-normal text-gray-600 normal-case">— just for display</span>
        </label>
        <input x-model="onboardingName" placeholder="my-app" class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
      </div>
      <div class="flex items-center justify-between">
        <button @click="onboardingStep = 3" class="text-xs text-gray-500 hover:text-gray-400">I'll do this later</button>
        <div class="flex gap-2">
          <button @click="onboardingStep = 1" class="px-4 py-2 text-sm rounded-lg bg-gray-800 text-gray-400 hover:text-white">Back</button>
          <button @click="onboardingStep = 3" class="px-5 py-2 rounded-lg text-sm font-semibold text-white" style="background:linear-gradient(135deg,#1f6feb,#3fb950)">Continue →</button>
        </div>
      </div>
    </div>

    <!-- Step 3: API key -->
    <div x-show="onboardingStep === 3" x-init="checkGroqKey()" class="px-6 py-6">
      <div class="w-12 h-12 rounded-xl bg-purple-900/30 flex items-center justify-center text-2xl mb-4">🔑</div>
      <h2 class="text-lg font-bold mb-2">Connect your AI key</h2>
      <p class="text-sm text-gray-400 mb-4">Chronicler uses a <strong class="text-gray-200">free Groq API key</strong> to understand your changes. No credit card needed.</p>

      <!-- Auto-detected -->
      <div x-show="onboardingKeyDetected" class="bg-green-900/20 border border-green-900/40 rounded-lg px-4 py-3 text-sm text-green-400 mb-5">
        ✓ API key detected in your environment — you're all set!
      </div>

      <!-- Manual entry -->
      <div x-show="!onboardingKeyDetected" class="mb-5">
        <div class="bg-blue-900/20 border border-blue-900/40 rounded-lg px-4 py-3 text-xs text-gray-400 mb-4">
          💡 Get a free key at <a href="https://console.groq.com/keys" target="_blank" class="text-blue-400 hover:underline">console.groq.com/keys</a>
        </div>
        <label class="text-xs font-semibold text-gray-500 uppercase tracking-wider block mb-1.5">Groq API key</label>
        <input x-model="onboardingKey" type="password" placeholder="gsk_..." class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
      </div>

      <div class="flex items-center justify-between">
        <button @click="onboardingStep = 4" class="text-xs text-gray-500 hover:text-gray-400">Skip — I'll add it later</button>
        <div class="flex gap-2">
          <button @click="onboardingStep = 2" class="px-4 py-2 text-sm rounded-lg bg-gray-800 text-gray-400 hover:text-white">Back</button>
          <button @click="onboardingStep = 4" class="px-5 py-2 rounded-lg text-sm font-semibold text-white" style="background:linear-gradient(135deg,#1f6feb,#3fb950)">Continue →</button>
        </div>
      </div>
    </div>

    <!-- Step 4: Done -->
    <div x-show="onboardingStep === 4" class="px-6 py-6">
      <div class="w-12 h-12 rounded-xl bg-yellow-900/30 flex items-center justify-center text-2xl mb-4">✦</div>
      <h2 class="text-lg font-bold mb-2">You're all set!</h2>
      <p class="text-sm text-gray-400 mb-5" x-text="onboardingPath ? `Chronicler is ready to watch ${onboardingName || onboardingPath.split('/').pop()}.` : 'Chronicler is ready to use.'"></p>
      <div class="bg-green-900/10 border border-green-900/30 rounded-lg px-4 py-3 space-y-2 mb-6">
        <div class="flex items-center gap-2 text-sm" x-show="onboardingPath">
          <span class="text-green-400">✓</span> <span class="text-gray-300" x-text="`Watching ${onboardingName || onboardingPath.split('/').pop()}`"></span>
        </div>
        <div class="flex items-center gap-2 text-sm" x-show="onboardingKeyDetected || onboardingKey">
          <span class="text-green-400">✓</span> <span class="text-gray-300">API key connected</span>
        </div>
        <div class="flex items-center gap-2 text-sm text-gray-500">
          <span>○</span> Add more projects any time with <strong class="text-gray-400">＋ Add project</strong>
        </div>
        <div class="flex items-center gap-2 text-sm text-gray-500">
          <span>○</span> Generate a handoff with <strong class="text-gray-400">✦ Generate Handoff</strong> before handing to an AI
        </div>
      </div>
      <div class="flex justify-end">
        <button @click="completeOnboarding()" class="px-5 py-2 rounded-lg text-sm font-semibold text-white" style="background:linear-gradient(135deg,#3fb950,#2ea043)">Open dashboard →</button>
      </div>
    </div>

  </div>
</div>
```

- [ ] **Step 3: Verify onboarding flow**

To test onboarding:
1. Stop the server
2. Temporarily rename `~/.config/chronicler/chronicler.db` to `chronicler.db.bak`
3. Restart the server: `chronicler ui`
4. Reload the browser — onboarding modal should appear
5. Walk through all 4 steps, add a project, verify it appears in the dashboard
6. Restore your database: `mv ~/.config/chronicler/chronicler.db.bak ~/.config/chronicler/chronicler.db`
7. Restart the server — no onboarding should appear

- [ ] **Step 4: Run full test suite to confirm nothing broken**

```bash
pytest -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add chronicler/ui/static/index.html
git commit -m "feat: add 4-step onboarding modal and contextual help tooltips"
```

---

## Final verification

- [ ] **Run full test suite**

```bash
pytest -v
```

Expected: all tests PASS

- [ ] **Manual end-to-end smoke test**

```bash
chronicler ui
```

Verify in browser:
1. Projects panel shows watched projects with correct traffic light colours
2. Clicking a traffic light starts/stops the daemon
3. Activity feed shows recent changes; filter pills work
4. Full Log tab shows session-grouped entries; search and diff expand work
5. ✦ Generate Handoff button works and shows markdown modal
6. View Map button shows the CHRONICLER_MAP.md
7. ＋ Add project modal works (enter a real path and add it)
8. Save a file in a watched project → within ~15 seconds a new entry appears in the feed

- [ ] **Push to GitHub**

```bash
git push
```
