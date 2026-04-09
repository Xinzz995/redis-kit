from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConnectionConfig:
    """Redis connection configuration. Immutable after creation."""

    url: str | None = None
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    max_connections: int = 10
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    decode_responses: bool = False
    ssl: bool = False


@dataclass(frozen=True)
class NamespaceConfig:
    """Key namespace configuration for transparent prefixing."""

    prefix: str = ""
    separator: str = ":"

    def build_key(self, *parts: str) -> str:
        """Build a namespaced Redis key from parts."""
        all_parts = (self.prefix, *parts) if self.prefix else parts
        return self.separator.join(all_parts)
