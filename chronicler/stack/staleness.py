from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from chronicler.stack.extractor import _hash_manifests
from chronicler.stack.schema import TechStack

_DEFAULT_MAX_AGE_DAYS = 30

_CATEGORY_HINTS: list[tuple[str, str, str]] = [
    # (glob, category_that_should_exist, human_readable_note)
    ("tailwind.config*", "color", "tailwind.config.* found but no color entries"),
    ("tailwind.config*", "font", "tailwind.config.* found but no font entries"),
    (".env.example",      "service", ".env.example found but no service entries"),
]


@dataclass
class StalenessResult:
    is_stale: bool
    reasons: list[str] = field(default_factory=list)


def check_staleness(
    stack: TechStack,
    project_path: Path,
    max_age_days: int = _DEFAULT_MAX_AGE_DAYS,
) -> StalenessResult:
    reasons: list[str] = []

    # 1. Manifest hash check
    current_hash = _hash_manifests(project_path)
    if current_hash != stack.manifest_hash:
        reasons.append(
            "Manifest files changed since last scan (manifest hash mismatch)"
        )

    # 2. Entry age check
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    stale_keys = [
        e.key for e in stack.entries
        if (
            e.last_verified.replace(tzinfo=timezone.utc)
            if e.last_verified.tzinfo is None
            else e.last_verified
        ) < cutoff
    ]
    if stale_keys:
        reasons.append(
            f"{len(stale_keys)} entries not verified in over {max_age_days} days: "
            + ", ".join(stale_keys[:5])
            + ("..." if len(stale_keys) > 5 else "")
        )

    # 3. Missing category detection
    existing_categories = {e.category for e in stack.entries}
    for glob, category, note in _CATEGORY_HINTS:
        if list(project_path.glob(glob)) and category not in existing_categories:
            reasons.append(note)

    return StalenessResult(is_stale=bool(reasons), reasons=reasons)
