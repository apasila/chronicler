from __future__ import annotations
import json
import sqlite3
import threading
from pathlib import Path
from datetime import datetime
from chronicler.storage.schema import LogEntry, FileInfo, ChangeInfo, LLMInfo, Session, Project


def _parse_dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


class Database:
    def __init__(self, db_path: str):
        self.db_path = str(Path(db_path).expanduser())
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def initialize(self) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    git_enabled INTEGER NOT NULL,
                    primary_language TEXT NOT NULL,
                    languages TEXT NOT NULL,
                    framework TEXT,
                    description TEXT,
                    log_mode TEXT NOT NULL,
                    ignore_patterns TEXT NOT NULL,
                    tags TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    duration_minutes INTEGER,
                    entry_count INTEGER NOT NULL DEFAULT 0,
                    files_touched TEXT NOT NULL,
                    primary_change_type TEXT,
                    session_summary TEXT,
                    session_health TEXT,
                    key_decisions TEXT NOT NULL,
                    open_threads TEXT NOT NULL,
                    handoff_generated INTEGER NOT NULL DEFAULT 0,
                    tokens_used INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                );
                CREATE TABLE IF NOT EXISTS log_entries (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_relative_path TEXT NOT NULL,
                    file_extension TEXT NOT NULL,
                    file_language TEXT NOT NULL,
                    file_is_new INTEGER NOT NULL,
                    file_is_deleted INTEGER NOT NULL,
                    file_is_renamed INTEGER NOT NULL,
                    file_renamed_from TEXT,
                    change_type TEXT NOT NULL,
                    change_subtype TEXT,
                    change_confidence REAL NOT NULL,
                    change_summary TEXT NOT NULL,
                    change_impact TEXT NOT NULL,
                    change_lines_added INTEGER NOT NULL,
                    change_lines_removed INTEGER NOT NULL,
                    change_diff_snapshot TEXT NOT NULL,
                    change_affected_functions TEXT,
                    change_affected_components TEXT,
                    llm_model TEXT NOT NULL,
                    llm_tokens_used INTEGER NOT NULL,
                    llm_prompt_version TEXT NOT NULL,
                    llm_processing_ms INTEGER NOT NULL,
                    context_json TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    manually_edited INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(id),
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );
                CREATE INDEX IF NOT EXISTS idx_entries_project ON log_entries(project_id);
                CREATE INDEX IF NOT EXISTS idx_entries_file ON log_entries(file_relative_path);
                CREATE INDEX IF NOT EXISTS idx_entries_timestamp ON log_entries(timestamp);
            """)
            conn.commit()

    def get_table_names(self) -> list[str]:
        rows = self._get_conn().execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return [r["name"] for r in rows]

    def insert_project(self, project: Project) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute("""
                INSERT OR REPLACE INTO projects
                (id, name, path, created_at, git_enabled, primary_language,
                 languages, framework, description, log_mode, ignore_patterns, tags)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                project.id, project.name, project.path,
                project.created_at.isoformat(), int(project.git_enabled),
                project.primary_language, json.dumps(project.languages),
                project.framework, project.description, project.log_mode,
                json.dumps(project.ignore_patterns), json.dumps(project.tags),
            ))
            conn.commit()

    def get_project(self, project_id: str) -> Project | None:
        row = self._get_conn().execute(
            "SELECT * FROM projects WHERE id=?", (project_id,)
        ).fetchone()
        return self._row_to_project(row) if row else None

    def get_project_by_path(self, path: str) -> Project | None:
        row = self._get_conn().execute(
            "SELECT * FROM projects WHERE path=?", (path,)
        ).fetchone()
        return self._row_to_project(row) if row else None

    def _row_to_project(self, row: sqlite3.Row) -> Project:
        return Project(
            id=row["id"], name=row["name"], path=row["path"],
            created_at=datetime.fromisoformat(row["created_at"]),
            git_enabled=bool(row["git_enabled"]),
            primary_language=row["primary_language"],
            languages=json.loads(row["languages"]),
            framework=row["framework"], description=row["description"],
            log_mode=row["log_mode"],
            ignore_patterns=json.loads(row["ignore_patterns"]),
            tags=json.loads(row["tags"]),
        )

    def insert_session(self, session: Session) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute("""
                INSERT OR REPLACE INTO sessions
                (id, project_id, started_at, ended_at, duration_minutes, entry_count,
                 files_touched, primary_change_type, session_summary, session_health,
                 key_decisions, open_threads, handoff_generated, tokens_used)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                session.id, session.project_id, session.started_at.isoformat(),
                session.ended_at.isoformat() if session.ended_at else None,
                session.duration_minutes, session.entry_count,
                json.dumps(session.files_touched), session.primary_change_type,
                session.session_summary, session.session_health,
                json.dumps(session.key_decisions), json.dumps(session.open_threads),
                int(session.handoff_generated), session.tokens_used,
            ))
            conn.commit()

    def get_session(self, session_id: str) -> Session | None:
        row = self._get_conn().execute(
            "SELECT * FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        return Session(
            id=row["id"], project_id=row["project_id"],
            started_at=datetime.fromisoformat(row["started_at"]),
            ended_at=_parse_dt(row["ended_at"]),
            duration_minutes=row["duration_minutes"],
            entry_count=row["entry_count"],
            files_touched=json.loads(row["files_touched"]),
            primary_change_type=row["primary_change_type"],
            session_summary=row["session_summary"],
            session_health=row["session_health"],
            key_decisions=json.loads(row["key_decisions"]),
            open_threads=json.loads(row["open_threads"]),
            handoff_generated=bool(row["handoff_generated"]),
            tokens_used=row["tokens_used"],
        )

    def get_active_session(self, project_id: str) -> Session | None:
        row = self._get_conn().execute("""
            SELECT * FROM sessions WHERE project_id=? AND ended_at IS NULL
            ORDER BY started_at DESC LIMIT 1
        """, (project_id,)).fetchone()
        return self.get_session(row["id"]) if row else None

    def update_session(self, session: Session) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute("""
                UPDATE sessions SET ended_at=?, duration_minutes=?, entry_count=?,
                files_touched=?, primary_change_type=?, session_summary=?,
                session_health=?, key_decisions=?, open_threads=?,
                handoff_generated=?, tokens_used=?
                WHERE id=?
            """, (
                session.ended_at.isoformat() if session.ended_at else None,
                session.duration_minutes, session.entry_count,
                json.dumps(session.files_touched), session.primary_change_type,
                session.session_summary, session.session_health,
                json.dumps(session.key_decisions), json.dumps(session.open_threads),
                int(session.handoff_generated), session.tokens_used,
                session.id,
            ))
            conn.commit()

    def get_recent_sessions(self, project_id: str, limit: int = 5) -> list[Session]:
        rows = self._get_conn().execute("""
            SELECT id FROM sessions WHERE project_id=?
            ORDER BY started_at DESC LIMIT ?
        """, (project_id, limit)).fetchall()
        return [s for r in rows if (s := self.get_session(r["id"])) is not None]

    def insert_log_entry(self, entry: LogEntry) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute("""
                INSERT OR REPLACE INTO log_entries
                (id, project_id, session_id, timestamp,
                 file_path, file_relative_path, file_extension, file_language,
                 file_is_new, file_is_deleted, file_is_renamed, file_renamed_from,
                 change_type, change_subtype, change_confidence, change_summary,
                 change_impact, change_lines_added, change_lines_removed, change_diff_snapshot,
                 change_affected_functions, change_affected_components,
                 llm_model, llm_tokens_used, llm_prompt_version, llm_processing_ms,
                 context_json, tags, manually_edited, notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                entry.id, entry.project_id, entry.session_id, entry.timestamp.isoformat(),
                entry.file.path, entry.file.relative_path, entry.file.extension,
                entry.file.language, int(entry.file.is_new), int(entry.file.is_deleted),
                int(entry.file.is_renamed), entry.file.renamed_from,
                entry.change.type, entry.change.subtype, entry.change.confidence,
                entry.change.summary, entry.change.impact, entry.change.lines_added,
                entry.change.lines_removed, entry.change.diff_snapshot,
                json.dumps(entry.change.affected_functions),
                json.dumps(entry.change.affected_components),
                entry.llm.model, entry.llm.tokens_used, entry.llm.prompt_version,
                entry.llm.processing_ms, json.dumps(entry.context),
                json.dumps(entry.tags), int(entry.manually_edited), entry.notes,
            ))
            conn.commit()

    def get_log_entry(self, entry_id: str) -> LogEntry | None:
        row = self._get_conn().execute(
            "SELECT * FROM log_entries WHERE id=?", (entry_id,)
        ).fetchone()
        return self._row_to_entry(row) if row else None

    def get_recent_entries_for_file(
        self, relative_path: str, project_id: str, limit: int = 3
    ) -> list[LogEntry]:
        rows = self._get_conn().execute("""
            SELECT * FROM log_entries
            WHERE file_relative_path=? AND project_id=?
            ORDER BY timestamp DESC LIMIT ?
        """, (relative_path, project_id, limit)).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_recent_entries(self, project_id: str, limit: int = 20) -> list[LogEntry]:
        rows = self._get_conn().execute("""
            SELECT * FROM log_entries WHERE project_id=?
            ORDER BY timestamp DESC LIMIT ?
        """, (project_id, limit)).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def _row_to_entry(self, row: sqlite3.Row) -> LogEntry:
        return LogEntry(
            id=row["id"], project_id=row["project_id"], session_id=row["session_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            file=FileInfo(
                path=row["file_path"], relative_path=row["file_relative_path"],
                extension=row["file_extension"], language=row["file_language"],
                is_new=bool(row["file_is_new"]), is_deleted=bool(row["file_is_deleted"]),
                is_renamed=bool(row["file_is_renamed"]), renamed_from=row["file_renamed_from"],
            ),
            change=ChangeInfo(
                type=row["change_type"], subtype=row["change_subtype"],
                confidence=row["change_confidence"], summary=row["change_summary"],
                impact=row["change_impact"], lines_added=row["change_lines_added"],
                lines_removed=row["change_lines_removed"],
                diff_snapshot=row["change_diff_snapshot"],
                affected_functions=json.loads(row["change_affected_functions"] or "null"),
                affected_components=json.loads(row["change_affected_components"] or "null"),
            ),
            llm=LLMInfo(
                model=row["llm_model"], tokens_used=row["llm_tokens_used"],
                prompt_version=row["llm_prompt_version"], processing_ms=row["llm_processing_ms"],
            ),
            context=json.loads(row["context_json"]),
            tags=json.loads(row["tags"]),
            manually_edited=bool(row["manually_edited"]),
            notes=row["notes"],
        )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
