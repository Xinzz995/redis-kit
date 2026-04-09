from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CommandHook(Protocol):
    """Protocol for observing Redis command execution."""

    def before(self, command: str, key: str, args: tuple) -> None: ...
    def after(self, command: str, key: str, result: Any, duration_ms: float) -> None: ...
    def on_error(self, command: str, key: str, error: Exception) -> None: ...


class CompositeHook:
    """Chains multiple hooks together."""

    def __init__(self, *hooks: CommandHook) -> None:
        self._hooks = hooks

    def before(self, command: str, key: str, args: tuple) -> None:
        for hook in self._hooks:
            hook.before(command, key, args)

    def after(self, command: str, key: str, result: Any, duration_ms: float) -> None:
        for hook in self._hooks:
            hook.after(command, key, result, duration_ms)

    def on_error(self, command: str, key: str, error: Exception) -> None:
        for hook in self._hooks:
            hook.on_error(command, key, error)
