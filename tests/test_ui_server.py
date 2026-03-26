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
