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
