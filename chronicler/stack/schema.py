from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel

STACK_CATEGORIES = [
    "language", "runtime", "framework", "library",
    "service", "font", "color", "icons", "tooling", "devops",
]


class StackEntry(BaseModel):
    key: str
    category: str
    value: str
    source: str          # e.g. "package.json", "llm_inference"
    confidence: float    # 0.0–1.0
    detected_at: datetime
    last_verified: datetime
    reason: str | None = None   # populated only for llm_inference entries


class TechStack(BaseModel):
    generated_at: datetime
    manifest_hash: str           # SHA-256 of all manifest file contents concatenated
    entries: list[StackEntry]
    constraints: list[str] = []  # human-authored, survives regeneration
