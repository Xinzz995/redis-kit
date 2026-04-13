from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RateLimitResult:
    """Rate limit check result, maps to standard HTTP rate limit headers."""

    allowed: bool
    limit: int
    remaining: int
    retry_after: float
    reset_at: float

    @classmethod
    def from_lua(cls, result: list[Any]) -> RateLimitResult:
        """Construct from a Lua script return value [allowed, limit, remaining, retry_after_ms, reset_at_ms]."""
        return cls(
            allowed=bool(result[0]),
            limit=int(result[1]),
            remaining=int(result[2]),
            retry_after=int(result[3]) / 1000.0,
            reset_at=int(result[4]) / 1000.0,
        )
