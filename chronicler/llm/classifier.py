from __future__ import annotations
import json
from chronicler.config.settings import Config
from chronicler.core.differ import DiffResult
from chronicler.llm.client import LLMClient
from chronicler.llm.prompts import (
    SYSTEM_PROMPT_ENTRY_CLASSIFIER, USER_PROMPT_ENTRY_CLASSIFIER,
    SYSTEM_PROMPT_SESSION_SUMMARIZER, USER_PROMPT_SESSION_SUMMARIZER,
    SYSTEM_PROMPT_MAP_UPDATER, USER_PROMPT_MAP_UPDATER,
    SYSTEM_PROMPT_HANDOFF_GENERATOR, USER_PROMPT_HANDOFF_GENERATOR,
    PROMPT_VERSIONS,
)
from chronicler.storage.schema import ChangeInfo, LLMInfo, CHANGE_TYPES


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end = -1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end])
    return text


class EntryClassifier:
    def __init__(self, config: Config):
        self.config = config
        self.client = LLMClient(config)

    def classify(
        self,
        diff: DiffResult,
        project_name: str,
        framework: str | None,
        recent_context: list[dict],
    ) -> tuple[ChangeInfo, LLMInfo]:
        user_prompt = USER_PROMPT_ENTRY_CLASSIFIER.format(
            project_name=project_name,
            framework=framework or "unknown",
            file_path=diff.relative_path,
            language=diff.language,
            diff=diff.diff_text[:3000],
            recent_context=json.dumps(recent_context, indent=2),
        )
        text, tokens, elapsed_ms = self.client.complete(
            task="entry_classifier",
            system_prompt=SYSTEM_PROMPT_ENTRY_CLASSIFIER,
            user_prompt=user_prompt,
            temperature=0.1,
        )
        parsed = self._parse(text)
        change_type = parsed.get("change_type", "experiment")
        if change_type not in CHANGE_TYPES:
            change_type = "experiment"

        change_info = ChangeInfo(
            type=change_type,
            subtype=parsed.get("subtype"),
            confidence=float(parsed.get("confidence", 0.5)),
            summary=str(parsed.get("summary", "Code changed"))[:120],
            impact=parsed.get("impact", "low") if parsed.get("impact") in ["low", "medium", "high"] else "low",
            lines_added=diff.lines_added,
            lines_removed=diff.lines_removed,
            diff_snapshot=diff.diff_text[:2000],
            affected_functions=parsed.get("affected_functions"),
            affected_components=parsed.get("affected_components"),
        )
        llm_info = LLMInfo(
            model=self.config.models.workhorse,
            tokens_used=tokens,
            prompt_version=PROMPT_VERSIONS["entry_classifier"],
            processing_ms=elapsed_ms,
        )
        return change_info, llm_info

    def _parse(self, text: str) -> dict:
        try:
            return json.loads(_strip_fences(text))
        except json.JSONDecodeError:
            return {}


class SessionSummarizer:
    def __init__(self, config: Config):
        self.config = config
        self.client = LLMClient(config)

    def summarize(self, session, project_name: str, entries: list) -> dict:
        entries_json = json.dumps([
            {"type": e.change.type, "summary": e.change.summary,
             "file": e.file.relative_path, "impact": e.change.impact}
            for e in entries
        ], indent=2)
        user_prompt = USER_PROMPT_SESSION_SUMMARIZER.format(
            project_name=project_name,
            duration_minutes=session.duration_minutes or 0,
            entry_count=len(entries),
            entries_json=entries_json,
        )
        text, _, _ = self.client.complete(
            task="session_summarizer",
            system_prompt=SYSTEM_PROMPT_SESSION_SUMMARIZER,
            user_prompt=user_prompt,
            temperature=0.2,
        )
        try:
            return json.loads(_strip_fences(text))
        except Exception:
            return {}


class MapUpdater:
    def __init__(self, config: Config):
        self.config = config
        self.client = LLMClient(config)

    def update(self, current_map: str, triggering_entries: list) -> dict:
        """Returns the parsed updates dict from the LLM, or empty dict on failure."""
        user_prompt = USER_PROMPT_MAP_UPDATER.format(
            current_map_json=json.dumps(current_map),
            triggering_entries_json=json.dumps([
                {"file": e.file.relative_path, "type": e.change.type,
                 "summary": e.change.summary}
                for e in triggering_entries
            ], indent=2),
        )
        text, _, _ = self.client.complete(
            task="map_updater",
            system_prompt=SYSTEM_PROMPT_MAP_UPDATER,
            user_prompt=user_prompt,
            temperature=0.1,
        )
        try:
            parsed = json.loads(_strip_fences(text))
            return parsed.get("updates", {})
        except Exception:
            return {}


class HandoffGenerator:
    def __init__(self, config: Config):
        self.config = config
        self.client = LLMClient(config)

    def generate(self, project, master_map: str, db, session_count: int = 5) -> str:
        sessions = db.get_recent_sessions(project.id, limit=session_count)
        sessions_data = [
            {"started_at": s.started_at.isoformat(), "summary": s.session_summary,
             "health": s.session_health, "key_decisions": s.key_decisions,
             "open_threads": s.open_threads, "files_touched": s.files_touched[:10]}
            for s in sessions
        ]
        entries = db.get_recent_entries(project.id, limit=30)
        key_entries = [
            {"timestamp": e.timestamp.isoformat(), "file": e.file.relative_path,
             "type": e.change.type, "summary": e.change.summary, "impact": e.change.impact}
            for e in entries if e.change.impact == "high"
        ][:10]

        system = SYSTEM_PROMPT_HANDOFF_GENERATOR.format(session_count=session_count)
        user_prompt = USER_PROMPT_HANDOFF_GENERATOR.format(
            project_name=project.name,
            framework=project.framework or "unknown",
            languages=", ".join(project.languages) or "unknown",
            master_map=master_map or "(no map yet)",
            session_count=len(sessions),
            sessions_json=json.dumps(sessions_data, indent=2),
            key_entries_json=json.dumps(key_entries, indent=2),
        )
        text, _, _ = self.client.complete(
            task="handoff_generator",
            system_prompt=system,
            user_prompt=user_prompt,
            temperature=0.3,
        )
        return text
