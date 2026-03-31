from __future__ import annotations
import asyncio
import json
import os
import uuid
import toml
from datetime import datetime
from pathlib import Path
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from chronicler.storage.db import Database
from chronicler.core.daemon import get_daemon_status, start_daemon, stop_daemon
from chronicler.storage.schema import Project
from chronicler.storage.map import MapManager
from chronicler.cli.main import _detect_framework
from chronicler.config.settings import load_config
from chronicler.llm.classifier import HandoffGenerator

STATIC_DIR = Path(__file__).parent / "static"


class AddProjectRequest(BaseModel):
    path: str
    name: str


class ProviderConfigRequest(BaseModel):
    provider: str
    groq_key: str = ""
    groq_model: str = "groq/llama-3.3-70b-versatile"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "phi4"
    custom_base_url: str = "http://localhost:8080/v1"
    custom_api_key: str = ""
    custom_model: str = "local-model"
    ignore_patterns: list[str] = []
    handoff_inbox: str = ""


class GroqKeyRequest(BaseModel):
    key: str


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
            counts = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN date(timestamp) = date('now') THEN 1 ELSE 0 END) as today
                FROM log_entries WHERE project_id = ?
            """, (row["id"],)).fetchone()
            result.append({
                "id": row["id"],
                "name": row["name"],
                "path": row["path"],
                "framework": row["framework"] or "",
                "log_mode": row["log_mode"],
                "status": get_daemon_status(project_path),
                "total_changes": counts["total"],
                "today_changes": counts["today"] or 0,
            })
        return JSONResponse(result)

    @app.get("/api/browse")
    def browse_dirs(path: str = "~"):
        import os
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_dir():
            resolved = Path.home()
        try:
            entries = sorted(
                [d.name for d in resolved.iterdir() if d.is_dir() and not d.name.startswith(".")],
                key=str.lower,
            )
        except PermissionError:
            entries = []
        parent = str(resolved.parent) if resolved != resolved.parent else None
        return {"path": str(resolved), "parent": parent, "dirs": entries}

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
        error = start_daemon(Path(project.path))
        if error:
            raise HTTPException(status_code=500, detail=error)
        return {"status": "started"}

    @app.delete("/api/projects/{project_id}")
    def delete_project(project_id: str):
        project = db.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        stop_daemon(Path(project.path))
        db.delete_project(project_id)
        return {"status": "deleted"}

    @app.post("/api/projects/{project_id}/stop")
    def stop_project(project_id: str):
        project = db.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        stop_daemon(Path(project.path))
        return {"status": "stopped"}

    @app.get("/api/usage")
    def get_usage():
        # Pricing per million tokens (blended input+output estimate)
        PRICE_PER_M = {
            "groq/llama-3.1-8b-instant":    0.07,
            "groq/llama-3.3-70b-versatile": 0.70,
            "groq/mixtral-8x7b-32768":      0.24,
            "groq/gemma2-9b-it":            0.20,
        }
        conn = db._get_conn()

        # Totals by model
        by_model = conn.execute("""
            SELECT llm_model, COUNT(*) as calls,
                   SUM(llm_tokens_used) as tokens,
                   AVG(llm_processing_ms) as avg_ms
            FROM log_entries GROUP BY llm_model
        """).fetchall()

        # Daily totals (last 30 days)
        by_day = conn.execute("""
            SELECT strftime('%Y-%m-%d', timestamp) as day,
                   COUNT(*) as calls,
                   SUM(llm_tokens_used) as tokens
            FROM log_entries
            WHERE timestamp >= date('now', '-30 days')
            GROUP BY day ORDER BY day DESC
        """).fetchall()

        # By project
        by_project = conn.execute("""
            SELECT p.name, COUNT(*) as calls, SUM(e.llm_tokens_used) as tokens
            FROM log_entries e JOIN projects p ON p.id = e.project_id
            GROUP BY p.name ORDER BY tokens DESC
        """).fetchall()

        def cost(model, tokens):
            rate = PRICE_PER_M.get(model, 0.70)
            return round((tokens / 1_000_000) * rate, 4)

        total_tokens = sum(r["tokens"] or 0 for r in by_model)
        total_calls  = sum(r["calls"]  for r in by_model)
        total_cost   = sum(cost(r["llm_model"], r["tokens"] or 0) for r in by_model)

        return {
            "total_tokens": total_tokens,
            "total_calls":  total_calls,
            "total_cost":   total_cost,
            "by_model": [{
                "model":   r["llm_model"],
                "calls":   r["calls"],
                "tokens":  r["tokens"] or 0,
                "avg_ms":  round(r["avg_ms"] or 0),
                "cost":    cost(r["llm_model"], r["tokens"] or 0),
                "free":    r["llm_model"] not in PRICE_PER_M,
            } for r in by_model],
            "by_day": [{"day": r["day"], "calls": r["calls"], "tokens": r["tokens"] or 0}
                       for r in by_day],
            "by_project": [{"name": r["name"], "calls": r["calls"], "tokens": r["tokens"] or 0,
                            "cost": cost("groq/llama-3.1-8b-instant", r["tokens"] or 0)}
                           for r in by_project],
        }

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

            try:
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
                            yield f"data: {json.dumps(entry)}\n\n"
                            last_rowid = max(last_rowid, entry["rowid"])
            except asyncio.CancelledError:
                return

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

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

        # Deliver to agent inbox if configured
        inbox = config.delivery.handoff_inbox.strip()
        if inbox:
            import shutil
            inbox_dir = Path(inbox).expanduser()
            inbox_dir.mkdir(parents=True, exist_ok=True)
            safe_name = project.name.lower().replace(" ", "-")
            inbox_dir.joinpath(f"{safe_name}-latest-handoff.md").write_text(output)

        return {"markdown": output, "saved_to": str(out_path)}

    @app.get("/api/config/groq-key-status")
    def groq_key_status():
        detected = bool(os.environ.get("GROQ_API_KEY"))
        return {"detected": detected}

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
        global_config_path.parent.mkdir(parents=True, exist_ok=True)
        global_config_path.write_text(toml.dumps(config_data))
        return {"ok": True}

    @app.get("/api/config/provider")
    def get_provider_config():
        global_config_path = Path.home() / ".config" / "chronicler" / "config.toml"
        if global_config_path.exists():
            config_data = toml.loads(global_config_path.read_text())
        else:
            config_data = {}

        workhorse = config_data.get("models", {}).get("workhorse", "groq/llama-3.3-70b-versatile")
        if workhorse.startswith("ollama/"):
            provider = "ollama"
        elif workhorse.startswith("openai/"):
            provider = "custom"
        else:
            provider = "groq"

        groq_section = config_data.get("groq", {})
        groq_key = groq_section.get("api_key", "") or os.environ.get("GROQ_API_KEY", "")
        groq_key_set = bool(groq_key)

        ollama_section = config_data.get("ollama", {})
        custom_section = config_data.get("custom", {})

        # Derive model display values
        if provider == "groq":
            groq_model = workhorse
        else:
            groq_model = config_data.get("models", {}).get("workhorse", "groq/llama-3.3-70b-versatile")
            # Fall back to default if it's not a groq model
            if not groq_model.startswith("groq/"):
                groq_model = "groq/llama-3.3-70b-versatile"

        if provider == "ollama":
            ollama_model = workhorse.removeprefix("ollama/")
        else:
            ollama_model = ollama_section.get("workhorse_model", "phi4")

        if provider == "custom":
            custom_model = workhorse.removeprefix("openai/")
        else:
            custom_model = custom_section.get("model", "local-model")

        return {
            "provider": provider,
            "groq_key_set": groq_key_set,
            "groq_model": groq_model,
            "ollama_base_url": ollama_section.get("base_url", "http://localhost:11434"),
            "ollama_model": ollama_model,
            "custom_base_url": custom_section.get("base_url", "http://localhost:8080/v1"),
            "custom_api_key": "",  # never expose actual key
            "custom_model": custom_model,
            "ignore_patterns": load_config(str(Path.home()), str(Path.home() / ".config" / "chronicler")).ignore.patterns,
            "handoff_inbox": config_data.get("delivery", {}).get("handoff_inbox", ""),
        }

    @app.post("/api/config/provider")
    def set_provider_config(req: ProviderConfigRequest):
        global_config_path = Path.home() / ".config" / "chronicler" / "config.toml"
        if global_config_path.exists():
            config_data = toml.loads(global_config_path.read_text())
        else:
            config_data = {}

        # Determine the workhorse model string
        if req.provider == "groq":
            workhorse = req.groq_model
            premium = req.groq_model
        elif req.provider == "ollama":
            workhorse = f"ollama/{req.ollama_model}"
            premium = f"ollama/{req.ollama_model}"
        else:  # custom
            workhorse = f"openai/{req.custom_model}"
            premium = f"openai/{req.custom_model}"

        # Update [models]
        if "models" not in config_data:
            config_data["models"] = {}
        config_data["models"]["workhorse"] = workhorse
        config_data["models"]["premium"] = premium

        # Update [groq] — only write key if a new non-bullet value was provided
        if "groq" not in config_data:
            config_data["groq"] = {}
        if req.groq_key and "•" not in req.groq_key:
            config_data["groq"]["api_key"] = req.groq_key
            os.environ["GROQ_API_KEY"] = req.groq_key

        # Update [ollama]
        if "ollama" not in config_data:
            config_data["ollama"] = {}
        config_data["ollama"]["base_url"] = req.ollama_base_url
        config_data["ollama"]["workhorse_model"] = req.ollama_model
        config_data["ollama"]["premium_model"] = req.ollama_model
        config_data["ollama"]["enabled"] = req.provider == "ollama"

        # Update [custom]
        if "custom" not in config_data:
            config_data["custom"] = {}
        config_data["custom"]["base_url"] = req.custom_base_url
        config_data["custom"]["model"] = req.custom_model
        config_data["custom"]["enabled"] = req.provider == "custom"
        if req.custom_api_key and "•" not in req.custom_api_key:
            config_data["custom"]["api_key"] = req.custom_api_key
            os.environ["OPENAI_API_KEY"] = req.custom_api_key

        # Update [ignore] — only save user-added patterns (not built-in defaults)
        from chronicler.config.settings import DEFAULT_IGNORE_PATTERNS
        user_only = [p for p in req.ignore_patterns if p not in DEFAULT_IGNORE_PATTERNS]
        if "ignore" not in config_data:
            config_data["ignore"] = {}
        config_data["ignore"]["global_patterns"] = user_only

        # Update [delivery]
        if "delivery" not in config_data:
            config_data["delivery"] = {}
        config_data["delivery"]["handoff_inbox"] = req.handoff_inbox

        global_config_path.parent.mkdir(parents=True, exist_ok=True)
        global_config_path.write_text(toml.dumps(config_data))
        return {"ok": True}

    @app.get("/")
    def root():
        return FileResponse(str(STATIC_DIR / "index.html"))

    # Mount static files (CSS, JS if needed in future)
    if (STATIC_DIR).exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app
