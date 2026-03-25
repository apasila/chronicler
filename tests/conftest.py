import pytest
from datetime import datetime
from chronicler.storage.db import Database
from chronicler.storage.schema import (
    LogEntry, FileInfo, ChangeInfo, LLMInfo, Project, Session
)

@pytest.fixture
def tmp_db(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.initialize()
    return db

@pytest.fixture
def sample_project():
    return Project(
        id="proj-1", name="test-project", path="/tmp/test-project",
        created_at=datetime.utcnow(), git_enabled=False,
        primary_language="python", languages=["python"],
        framework=None, description=None, log_mode="debounced",
        ignore_patterns=[], tags=[],
    )

@pytest.fixture
def sample_session():
    return Session(
        id="sess-1", project_id="proj-1",
        started_at=datetime.utcnow(), ended_at=None, duration_minutes=None,
        entry_count=0, files_touched=[], primary_change_type=None,
        session_summary=None, session_health=None,
        key_decisions=[], open_threads=[], handoff_generated=False, tokens_used=0,
    )

@pytest.fixture
def sample_entry():
    return LogEntry(
        id="entry-1", project_id="proj-1", session_id="sess-1",
        timestamp=datetime.utcnow(),
        file=FileInfo(path="/tmp/test-project/app.py", relative_path="app.py",
                      extension=".py", language="python",
                      is_new=False, is_deleted=False, is_renamed=False, renamed_from=None),
        change=ChangeInfo(type="feature", subtype=None, confidence=0.9,
                          summary="Added hello world function", impact="low",
                          lines_added=5, lines_removed=0,
                          diff_snapshot="+def hello(): return 'world'",
                          affected_functions=["hello"], affected_components=None),
        llm=LLMInfo(model="test-model", tokens_used=500, prompt_version="1.0", processing_ms=200),
        context={"git_branch": "main"}, tags=["feature"],
        manually_edited=False, notes=None,
    )
