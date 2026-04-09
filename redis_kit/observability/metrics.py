from __future__ import annotations

from collections import defaultdict
from typing import Any


class MetricsCollector:
    """Collects Redis command metrics. Implements CommandHook protocol."""

    def __init__(self) -> None:
        self._commands: dict[str, int] = defaultdict(int)
        self._errors: int = 0
        self._latencies: list[float] = []

    def before(self, command: str, key: str, args: tuple) -> None:
        pass

    def after(self, command: str, key: str, result: Any, duration_ms: float) -> None:
        self._commands[command] += 1
        self._latencies.append(duration_ms)

    def on_error(self, command: str, key: str, error: Exception) -> None:
        self._errors += 1

    def command_count(self, command: str) -> int:
        return self._commands.get(command, 0)

    def error_count(self) -> int:
        return self._errors

    def latency_stats(self) -> dict[str, float]:
        if not self._latencies:
            return {"count": 0, "avg": 0, "min": 0, "max": 0}
        return {
            "count": len(self._latencies),
            "avg": sum(self._latencies) / len(self._latencies),
            "min": min(self._latencies),
            "max": max(self._latencies),
        }
