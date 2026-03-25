from __future__ import annotations
from datetime import datetime
from pathlib import Path

INITIAL_TEMPLATE = """# Chronicler Map — {project_name}
Last updated: {date}

## Project Overview
{overview_line}

## Feature Status
| Feature | Status | Last touched |
|---------|--------|--------------|
| (none yet) | — | — |

## Active Routes
(none detected yet)

## Dependencies (recent changes)
(none tracked yet)

## Known Issues
(none logged yet)

## Last 3 Sessions
(no sessions yet)
"""


class MapManager:
    def __init__(self, chronicler_dir: str):
        self.dir = Path(chronicler_dir)
        self.map_path = self.dir / "CHRONICLER_MAP.md"

    def create_initial(
        self, project_name: str, framework: str | None, languages: list[str]
    ) -> None:
        if framework:
            overview_line = f"Project using {framework}."
        elif languages:
            overview_line = f"Project using {', '.join(languages)}."
        else:
            overview_line = "Project overview not yet set."
        content = INITIAL_TEMPLATE.format(
            project_name=project_name,
            date=datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
            overview_line=overview_line,
        )
        self.map_path.write_text(content)

    def read(self) -> str:
        return self.map_path.read_text() if self.map_path.exists() else ""

    def update(self, updates: dict) -> None:
        content = self.read()
        if not content:
            return
        # Update timestamp
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("Last updated:"):
                lines[i] = f"Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
                break

        section_map = {
            "dependencies": "## Dependencies (recent changes)",
            "known_issues": "## Known Issues",
            "routes": "## Active Routes",
            "features": "## Feature Status",
        }
        content = "\n".join(lines)
        for key, header in section_map.items():
            if items := updates.get(key):
                content = self._replace_section(content, header, items)

        self.map_path.write_text(content)

    def _replace_section(self, content: str, header: str, items: list[str]) -> str:
        lines = content.splitlines()
        start = next((i + 1 for i, l in enumerate(lines) if l.strip() == header), None)
        if start is None:
            return content
        end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
        new_lines = lines[:start] + [f"- {item}" for item in items] + [""] + lines[end:]
        return "\n".join(new_lines)

    def append_session_summary(self, summary: str, date: str) -> None:
        content = self.read()
        marker = "## Last 3 Sessions\n"
        if marker not in content:
            return
        idx = content.index(marker) + len(marker)
        rest = content[idx:]
        existing_entries = [l for l in rest.splitlines() if l.startswith("- ")][:2]
        new_section = "\n".join([f"- {date}: {summary}"] + existing_entries)
        end_idx = next(
            (i for i, l in enumerate(rest.splitlines()) if l.startswith("## ")),
            len(rest.splitlines())
        )
        rest_lines = rest.splitlines()
        tail = "\n".join(rest_lines[end_idx:]) if end_idx < len(rest_lines) else ""
        self.map_path.write_text(content[:idx] + new_section + "\n" + tail)
