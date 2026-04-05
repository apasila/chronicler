from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, field_validator

CHANGE_TYPES = [
    "feature", "bug_fix", "refactor", "style", "config",
    "dependency", "test", "docs", "delete", "experiment",
]
CHANGE_SUBTYPES = [
    "logic_error", "type_error", "performance", "security",
    "ui_change", "api_change", "db_change", "routing_change",
]
IMPACT_LEVELS = ["low", "medium", "high"]
SESSION_HEALTH = ["productive", "exploratory", "debugging", "maintenance"]

MAP_TRIGGER_PATTERNS = [
    "package.json", "requirements.txt", "go.mod", "Cargo.toml",
    "pyproject.toml", "tsconfig.json",
    "tailwind.config.js", "tailwind.config.ts", "tailwind.config.mjs",
    ".env.example",
    "*.routes.*", "router.*", "app/api/**",
    "*.config.*", "README*",
]


class FileInfo(BaseModel):
    path: str
    relative_path: str
    extension: str
    language: str
    is_new: bool
    is_deleted: bool
    is_renamed: bool
    renamed_from: str | None


class ChangeInfo(BaseModel):
    type: str
    subtype: str | None
    confidence: float
    summary: str
    impact: str
    lines_added: int
    lines_removed: int
    diff_snapshot: str
    affected_functions: list[str] | None
    affected_components: list[str] | None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in CHANGE_TYPES:
            raise ValueError(f"type must be one of {CHANGE_TYPES}, got '{v}'")
        return v

    @field_validator("subtype")
    @classmethod
    def validate_subtype(cls, v: str | None) -> str | None:
        if v is not None and v not in CHANGE_SUBTYPES:
            raise ValueError(f"subtype must be one of {CHANGE_SUBTYPES} or null")
        return v

    @field_validator("impact")
    @classmethod
    def validate_impact(cls, v: str) -> str:
        if v not in IMPACT_LEVELS:
            raise ValueError(f"impact must be one of {IMPACT_LEVELS}")
        return v

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, v: str) -> str:
        if len(v) > 120:
            raise ValueError("summary must be 120 chars or fewer")
        return v


class LLMInfo(BaseModel):
    model: str
    tokens_used: int
    prompt_version: str
    processing_ms: int


class LogEntry(BaseModel):
    id: str
    project_id: str
    session_id: str
    timestamp: datetime
    file: FileInfo
    change: ChangeInfo
    llm: LLMInfo
    context: dict
    tags: list[str]
    manually_edited: bool
    notes: str | None


class Session(BaseModel):
    id: str
    project_id: str
    started_at: datetime
    ended_at: datetime | None
    duration_minutes: int | None
    entry_count: int
    files_touched: list[str]
    primary_change_type: str | None
    session_summary: str | None
    session_health: str | None
    key_decisions: list[str]
    open_threads: list[str]
    handoff_generated: bool
    tokens_used: int

    @field_validator("session_health")
    @classmethod
    def validate_health(cls, v: str | None) -> str | None:
        if v is not None and v not in SESSION_HEALTH:
            raise ValueError(f"session_health must be one of {SESSION_HEALTH}")
        return v


class Project(BaseModel):
    id: str
    name: str
    path: str
    created_at: datetime
    git_enabled: bool
    primary_language: str
    languages: list[str]
    framework: str | None
    description: str | None
    log_mode: str
    ignore_patterns: list[str]
    tags: list[str]
