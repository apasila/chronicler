from __future__ import annotations
import threading
from typing import Callable


class Debouncer:
    """Fires callback(path) once per file after no new events for delay_seconds."""

    def __init__(self, delay_seconds: float, callback: Callable[[str], None]):
        self.delay = delay_seconds
        self.callback = callback
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()
        self._shutdown = False

    def trigger(self, path: str) -> None:
        if self._shutdown:
            return
        with self._lock:
            if path in self._timers:
                self._timers[path].cancel()
            timer = threading.Timer(self.delay, self._fire, args=[path])
            self._timers[path] = timer
            timer.start()

    def _fire(self, path: str) -> None:
        with self._lock:
            self._timers.pop(path, None)
        if not self._shutdown:
            self.callback(path)

    def shutdown(self) -> None:
        self._shutdown = True
        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()
