from __future__ import annotations
from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, Field, field_validator

STACK_CATEGORIES = [
    "language", "runtime", "framework", "library",
    "service", "font", "color", "icons", "tooling", "devops",
]


class StackEntry(BaseModel):
    key: str
    category: str
    value: str
    source: str          # e.g. "package.json", "llm_inference"
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    detected_at: datetime
    last_verified: datetime
    reason: str | None = None   # populated only for llm_inference entries

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in STACK_CATEGORIES:
            raise ValueError(f"category must be one of {STACK_CATEGORIES}, got '{v}'")
        return v


class TechStack(BaseModel):
    generated_at: datetime
    manifest_hash: str           # SHA-256 of all manifest file contents concatenated
    entries: list[StackEntry]
    constraints: list[str] = []  # human-authored, survives regeneration
