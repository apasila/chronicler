from __future__ import annotations
import fnmatch
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from chronicler.core.debouncer import Debouncer


class _Handler(FileSystemEventHandler):
    def __init__(self, watcher: "Watcher"):
        super().__init__()
        self._watcher = watcher

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._handle(str(event.src_path))

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._handle(str(event.src_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._handle(str(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._handle(str(event.dest_path))


class Watcher:
    def __init__(
        self,
        project_path: str,
        ignore_patterns: list[str],
        on_change: Callable[[str], None],
        debounce_seconds: float = 10.0,
    ):
        self.project_path = Path(project_path).resolve()
        self.ignore_patterns = ignore_patterns
        self._debouncer = Debouncer(delay_seconds=debounce_seconds, callback=on_change)
        self._observer: Observer | None = None

    def should_ignore(self, file_path: str) -> bool:
        p = Path(file_path)
        try:
            rel = str(p.relative_to(self.project_path))
        except ValueError:
            rel = p.name
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(p.name, pattern):
                return True
            # Handle dir/** patterns like node_modules/**
            parts = pattern.split("/**")
            if len(parts) == 2 and rel.startswith(parts[0] + "/"):
                return True
        return False

    def _handle(self, file_path: str) -> None:
        if not self.should_ignore(file_path):
            self._debouncer.trigger(file_path)

    def start(self) -> None:
        self._observer = Observer()
        self._observer.schedule(_Handler(self), str(self.project_path), recursive=True)
        self._observer.start()

    def stop(self) -> None:
        self._debouncer.shutdown()
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None

    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()
