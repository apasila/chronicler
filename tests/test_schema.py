from datetime import datetime
import pytest
from chronicler.storage.schema import (
    FileInfo, ChangeInfo, LLMInfo, LogEntry, Session, Project, CHANGE_TYPES
)

def test_file_info_minimal():
    fi = FileInfo(
        path="/project/src/app.py", relative_path="src/app.py",
        extension=".py", language="python",
        is_new=False, is_deleted=False, is_renamed=False, renamed_from=None,
    )
    assert fi.extension == ".py"

def test_change_info_rejects_invalid_type():
    with pytest.raises(Exception):
        ChangeInfo(
            type="made_up_type", subtype=None, confidence=0.9,
            summary="Added login", impact="medium",
            lines_added=10, lines_removed=2, diff_snapshot="@@...",
            affected_functions=None, affected_components=None,
        )

def test_change_info_valid():
    ci = ChangeInfo(
        type="feature", subtype="api_change", confidence=0.95,
        summary="Added login endpoint", impact="medium",
        lines_added=10, lines_removed=2, diff_snapshot="@@...",
        affected_functions=["login"], affected_components=None,
    )
    assert ci.type == "feature"

def test_summary_max_120_chars():
    with pytest.raises(Exception):
        ChangeInfo(
            type="feature", subtype=None, confidence=0.9,
            summary="x" * 121, impact="low",
            lines_added=1, lines_removed=0, diff_snapshot="@@...",
            affected_functions=None, affected_components=None,
        )

def test_log_entry_roundtrip():
    now = datetime.utcnow()
    entry = LogEntry(
        id="abc-123", project_id="proj-1", session_id="sess-1", timestamp=now,
        file=FileInfo(path="/p/app.py", relative_path="app.py", extension=".py",
                      language="python", is_new=False, is_deleted=False,
                      is_renamed=False, renamed_from=None),
        change=ChangeInfo(type="bug_fix", subtype="logic_error", confidence=0.85,
                          summary="Fixed null pointer in login", impact="high",
                          lines_added=3, lines_removed=1, diff_snapshot="...",
                          affected_functions=["login"], affected_components=None),
        llm=LLMInfo(model="llama3", tokens_used=850, prompt_version="1.0", processing_ms=420),
        context={"git_branch": "main"}, tags=["auth"], manually_edited=False, notes=None,
    )
    assert entry.change.type == "bug_fix"
    assert entry.llm.tokens_used == 850
