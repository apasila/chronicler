from __future__ import annotations
import difflib
import subprocess
from dataclasses import dataclass
from pathlib import Path

LANGUAGE_MAP = {
    ".py": "python", ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".go": "go",
    ".rs": "rust", ".rb": "ruby", ".java": "java", ".cs": "csharp",
    ".cpp": "cpp", ".c": "c", ".swift": "swift", ".kt": "kotlin",
    ".php": "php", ".html": "html", ".css": "css", ".scss": "scss",
    ".md": "markdown", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".sh": "shell", ".bash": "shell", ".zsh": "shell",
}


@dataclass
class DiffResult:
    file_path: str
    relative_path: str
    diff_text: str
    lines_added: int
    lines_removed: int
    is_new_file: bool
    is_deleted: bool
    language: str


class Differ:
    def __init__(self, project_path: str, git_enabled: bool):
        self.project_path = Path(project_path)
        self.git_enabled = git_enabled
        self._snapshots: dict[str, list[str]] = {}

    def detect_language(self, filename: str) -> str:
        return LANGUAGE_MAP.get(Path(filename).suffix.lower(), "unknown")

    def store_snapshot(self, file_path: str) -> None:
        p = Path(file_path)
        self._snapshots[file_path] = (
            p.read_text(errors="replace").splitlines(keepends=True) if p.exists() else []
        )

    def diff_file(self, file_path: str) -> DiffResult | None:
        if self.git_enabled:
            return self._git_diff(file_path)
        return self._raw_diff(file_path)

    def _raw_diff(self, file_path: str) -> DiffResult:
        p = Path(file_path)
        try:
            rel = str(p.relative_to(self.project_path))
        except ValueError:
            rel = p.name
        lang = self.detect_language(p.name)

        if not p.exists():
            old = self._snapshots.get(file_path, [])
            diff_lines = list(difflib.unified_diff(old, [], fromfile=rel, tofile="/dev/null"))
            return DiffResult(file_path=file_path, relative_path=rel,
                              diff_text="".join(diff_lines), lines_added=0,
                              lines_removed=len(old), is_new_file=False,
                              is_deleted=True, language=lang)

        new_lines = p.read_text(errors="replace").splitlines(keepends=True)
        is_new = file_path not in self._snapshots
        old_lines = self._snapshots.get(file_path, [])

        if is_new:
            diff_text = "".join(f"+{l}" for l in new_lines)
            added, removed = len(new_lines), 0
        else:
            diff_lines = list(difflib.unified_diff(old_lines, new_lines,
                                                    fromfile=rel, tofile=rel))
            diff_text = "".join(diff_lines)
            added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
            removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))

        self._snapshots[file_path] = new_lines
        return DiffResult(file_path=file_path, relative_path=rel, diff_text=diff_text,
                          lines_added=added, lines_removed=removed,
                          is_new_file=is_new, is_deleted=False, language=lang)

    def _git_diff(self, file_path: str) -> DiffResult:
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD", "--", file_path],
                capture_output=True, text=True, cwd=str(self.project_path),
            )
            diff_text = result.stdout or self._read_as_new(file_path)
            return self._parse_unified_diff(file_path, diff_text)
        except Exception:
            return self._raw_diff(file_path)

    def _read_as_new(self, file_path: str) -> str:
        p = Path(file_path)
        if not p.exists():
            return ""
        return "".join(f"+{l}" for l in p.read_text(errors="replace").splitlines(keepends=True))

    def _parse_unified_diff(self, file_path: str, diff_text: str) -> DiffResult:
        p = Path(file_path)
        try:
            rel = str(p.relative_to(self.project_path))
        except ValueError:
            rel = p.name
        lines = diff_text.splitlines()
        added = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
        return DiffResult(file_path=file_path, relative_path=rel, diff_text=diff_text,
                          lines_added=added, lines_removed=removed,
                          is_new_file=False, is_deleted=False,
                          language=self.detect_language(p.name))
