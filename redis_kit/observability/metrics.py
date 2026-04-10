from __future__ import annotations

import threading
from collections import defaultdict, deque
from typing import Any


class MetricsCollector:
    """Collects Redis command metrics. Implements CommandHook protocol."""

    def __init__(self, max_latencies: int = 10000) -> None:
        self._lock = threading.Lock()
        self._commands: dict[str, int] = defaultdict(int)
        self._errors: int = 0
        self._latencies: deque[float] = deque(maxlen=max_latencies)

    def before(self, command: str, key: str, args: tuple) -> None:
        pass

    def after(self, command: str, key: str, result: Any, duration_ms: float) -> None:
        with self._lock:
            self._commands[command] += 1
            self._latencies.append(duration_ms)

    def on_error(self, command: str, key: str, error: Exception) -> None:
        with self._lock:
            self._errors += 1

    def command_count(self, command: str) -> int:
        with self._lock:
            return self._commands.get(command, 0)

    def error_count(self) -> int:
        with self._lock:
            return self._errors

    def latency_stats(self) -> dict[str, float]:
        with self._lock:
            if not self._latencies:
                return {"count": 0, "avg": 0, "min": 0, "max": 0}
            return {
                "count": len(self._latencies),
                "avg": sum(self._latencies) / len(self._latencies),
                "min": min(self._latencies),
                "max": max(self._latencies),
            }
