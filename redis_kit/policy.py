from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class FallbackPolicy:
    """Configurable degradation strategy for Redis failures."""

    on_connection_error: Literal["raise", "return_none", "callback"] = "raise"
    fallback: Callable[..., Any] | None = None
    log_on_fallback: bool = True
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("redis_kit"))

    def __post_init__(self) -> None:
        if self.on_connection_error == "callback" and self.fallback is None:
            raise ValueError("FallbackPolicy with on_connection_error='callback' requires a non-None fallback callable")
        if self.fallback is not None and not callable(self.fallback):
            raise TypeError(f"fallback must be callable, got {type(self.fallback).__name__}")
