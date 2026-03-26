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


def test_get_all_recent_entries_empty(tmp_db):
    results = tmp_db.get_all_recent_entries()
    assert results == []


def test_get_all_recent_entries_returns_dicts(tmp_db, sample_project, sample_session):
    from tests.conftest import make_entry
    tmp_db.insert_project(sample_project)
    tmp_db.insert_session(sample_session)
    tmp_db.insert_log_entry(make_entry(sample_project.id, sample_session.id, change_type="feature"))
    tmp_db.insert_log_entry(make_entry(sample_project.id, sample_session.id, change_type="bug_fix"))
    results = tmp_db.get_all_recent_entries(limit=10)
    assert len(results) == 2
    required = {"rowid", "id", "project_id", "project_name", "change_type",
                "change_summary", "file_relative_path", "change_impact",
                "timestamp", "session_id", "change_diff_snapshot"}
    for entry in results:
        assert required.issubset(entry.keys())


def test_get_all_recent_entries_filter_by_project(tmp_db, sample_project, sample_session):
    from tests.conftest import make_entry
    tmp_db.insert_project(sample_project)
    tmp_db.insert_session(sample_session)
    tmp_db.insert_log_entry(make_entry(sample_project.id, sample_session.id))
    results = tmp_db.get_all_recent_entries(project_id=sample_project.id)
    assert len(results) == 1
    assert tmp_db.get_all_recent_entries(project_id="nonexistent-id") == []


def test_get_all_recent_entries_filter_by_change_type(tmp_db, sample_project, sample_session):
    from tests.conftest import make_entry
    tmp_db.insert_project(sample_project)
    tmp_db.insert_session(sample_session)
    tmp_db.insert_log_entry(make_entry(sample_project.id, sample_session.id, change_type="feature"))
    tmp_db.insert_log_entry(make_entry(sample_project.id, sample_session.id, change_type="bug_fix"))
    results = tmp_db.get_all_recent_entries(change_type="feature")
    assert len(results) == 1
    assert results[0]["change_type"] == "feature"


def test_get_all_recent_entries_after_rowid(tmp_db, sample_project, sample_session):
    from tests.conftest import make_entry
    tmp_db.insert_project(sample_project)
    tmp_db.insert_session(sample_session)
    tmp_db.insert_log_entry(make_entry(sample_project.id, sample_session.id))
    tmp_db.insert_log_entry(make_entry(sample_project.id, sample_session.id))
    all_entries = tmp_db.get_all_recent_entries()
    assert len(all_entries) == 2
    min_rowid = min(e["rowid"] for e in all_entries)
    results = tmp_db.get_all_recent_entries(after_rowid=min_rowid)
    assert len(results) == 1
    assert results[0]["rowid"] > min_rowid
