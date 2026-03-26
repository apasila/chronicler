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
