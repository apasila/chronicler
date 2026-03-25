import pytest
from chronicler.storage.db import Database

def test_initialize_creates_tables(tmp_db):
    tables = tmp_db.get_table_names()
    assert "projects" in tables
    assert "sessions" in tables
    assert "log_entries" in tables

def test_insert_and_get_project(tmp_db, sample_project):
    tmp_db.insert_project(sample_project)
    retrieved = tmp_db.get_project(sample_project.id)
    assert retrieved is not None
    assert retrieved.name == "test-project"

def test_insert_and_get_session(tmp_db, sample_project, sample_session):
    tmp_db.insert_project(sample_project)
    tmp_db.insert_session(sample_session)
    retrieved = tmp_db.get_session(sample_session.id)
    assert retrieved is not None
    assert retrieved.project_id == "proj-1"

def test_insert_and_get_log_entry(tmp_db, sample_project, sample_session, sample_entry):
    tmp_db.insert_project(sample_project)
    tmp_db.insert_session(sample_session)
    tmp_db.insert_log_entry(sample_entry)
    retrieved = tmp_db.get_log_entry(sample_entry.id)
    assert retrieved is not None
    assert retrieved.change.type == "feature"
    assert retrieved.change.summary == "Added hello world function"

def test_get_recent_entries_for_file(tmp_db, sample_project, sample_session, sample_entry):
    tmp_db.insert_project(sample_project)
    tmp_db.insert_session(sample_session)
    tmp_db.insert_log_entry(sample_entry)
    entries = tmp_db.get_recent_entries_for_file("app.py", "proj-1", limit=5)
    assert len(entries) == 1
    assert entries[0].id == "entry-1"

def test_get_project_by_path(tmp_db, sample_project):
    tmp_db.insert_project(sample_project)
    found = tmp_db.get_project_by_path("/tmp/test-project")
    assert found is not None
    assert found.id == "proj-1"
