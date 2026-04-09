from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitResult:
    """Rate limit check result, maps to standard HTTP rate limit headers."""

    allowed: bool
    limit: int
    remaining: int
    retry_after: float
    reset_at: float
