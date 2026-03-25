from __future__ import annotations
import uuid
from datetime import datetime
from chronicler.storage.db import Database
from chronicler.storage.schema import Session


class ContextAssembler:
    def __init__(self, db: Database):
        self.db = db

    def get_recent_context(
        self, relative_path: str, project_id: str, limit: int = 3
    ) -> list[dict]:
        entries = self.db.get_recent_entries_for_file(relative_path, project_id, limit)
        return [
            {"timestamp": e.timestamp.isoformat(),
             "change_type": e.change.type,
             "summary": e.change.summary,
             "impact": e.change.impact}
            for e in entries
        ]

    def get_or_create_session(
        self, project_id: str, session_gap_minutes: int = 30
    ) -> Session:
        active = self.db.get_active_session(project_id)
        now = datetime.utcnow()

        if active is not None:
            elapsed_minutes = (now - active.started_at).total_seconds() / 60
            if elapsed_minutes < session_gap_minutes:
                return active
            # Close expired session
            active.ended_at = now
            active.duration_minutes = int(elapsed_minutes)
            self.db.update_session(active)

        new_session = Session(
            id=str(uuid.uuid4()),
            project_id=project_id,
            started_at=now,
            ended_at=None,
            duration_minutes=None,
            entry_count=0,
            files_touched=[],
            primary_change_type=None,
            session_summary=None,
            session_health=None,
            key_decisions=[],
            open_threads=[],
            handoff_generated=False,
            tokens_used=0,
        )
        self.db.insert_session(new_session)
        return new_session
