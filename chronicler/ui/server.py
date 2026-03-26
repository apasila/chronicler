from __future__ import annotations
import os
import uuid
import toml
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from chronicler.storage.db import Database
from chronicler.core.daemon import get_daemon_status, start_daemon, stop_daemon
from chronicler.storage.schema import Project
from chronicler.storage.map import MapManager
from chronicler.cli.main import _detect_framework

STATIC_DIR = Path(__file__).parent / "static"


class AddProjectRequest(BaseModel):
    path: str
    name: str


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

    @app.get("/")
    def root():
        return FileResponse(str(STATIC_DIR / "index.html"))

    # Mount static files (CSS, JS if needed in future)
    if (STATIC_DIR).exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app
