import pytest
from datetime import datetime
from chronicler.core.context import ContextAssembler


def test_get_recent_context_empty(tmp_db, sample_project):
    tmp_db.insert_project(sample_project)
    asm = ContextAssembler(db=tmp_db)
    result = asm.get_recent_context("app.py", "proj-1", limit=3)
    assert result == []


def test_get_recent_context_returns_entries(tmp_db, sample_project, sample_session, sample_entry):
    tmp_db.insert_project(sample_project)
    tmp_db.insert_session(sample_session)
    tmp_db.insert_log_entry(sample_entry)
    asm = ContextAssembler(db=tmp_db)
    result = asm.get_recent_context("app.py", "proj-1", limit=3)
    assert len(result) == 1
    assert result[0]["change_type"] == "feature"
    assert "summary" in result[0]


def test_get_or_create_session_creates_new(tmp_db, sample_project):
    tmp_db.insert_project(sample_project)
    asm = ContextAssembler(db=tmp_db)
    session = asm.get_or_create_session("proj-1", session_gap_minutes=30)
    assert session.id is not None
    assert session.project_id == "proj-1"
    assert session.ended_at is None


def test_get_or_create_session_reuses_active(tmp_db, sample_project):
    tmp_db.insert_project(sample_project)
    asm = ContextAssembler(db=tmp_db)
    s1 = asm.get_or_create_session("proj-1", session_gap_minutes=30)
    s2 = asm.get_or_create_session("proj-1", session_gap_minutes=30)
    assert s1.id == s2.id
