from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

_logger = logging.getLogger("redis_kit.hooks")


@runtime_checkable
class CommandHook(Protocol):
    """Protocol for observing Redis command execution.

    All methods are synchronous. Async operations call hooks synchronously;
    hook implementations that need async I/O should enqueue work rather than block.
    """

    def before(self, command: str, key: str, args: tuple) -> None: ...
    def after(self, command: str, key: str, result: Any, duration_ms: float) -> None: ...
    def on_error(self, command: str, key: str, error: Exception) -> None: ...


class CompositeHook:
    """Chains multiple hooks together."""

    def __init__(self, *hooks: CommandHook) -> None:
        self._hooks = hooks

    def before(self, command: str, key: str, args: tuple) -> None:
        for hook in self._hooks:
            try:
                hook.before(command, key, args)
            except Exception:
                _logger.exception("Hook before() failed for %s", type(hook).__name__)

    def after(self, command: str, key: str, result: Any, duration_ms: float) -> None:
        for hook in self._hooks:
            try:
                hook.after(command, key, result, duration_ms)
            except Exception:
                _logger.exception("Hook after() failed for %s", type(hook).__name__)

    def on_error(self, command: str, key: str, error: Exception) -> None:
        for hook in self._hooks:
            try:
                hook.on_error(command, key, error)
            except Exception:
                _logger.exception("Hook on_error() failed for %s", type(hook).__name__)
