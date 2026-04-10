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


@dataclass(frozen=True)
class SentinelConfig:
    """Redis Sentinel configuration."""

    sentinels: tuple[tuple[str, int], ...]
    service_name: str
    db: int = 0
    password: str | None = None
    sentinel_password: str | None = None
    max_connections: int = 10
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    decode_responses: bool = False
    ssl: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.sentinels, list):
            object.__setattr__(self, "sentinels", tuple(tuple(s) for s in self.sentinels))


@dataclass(frozen=True)
class ClusterConfig:
    """Redis Cluster configuration."""

    startup_nodes: tuple[tuple[str, int], ...]
    password: str | None = None
    max_connections: int = 10
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    decode_responses: bool = False
    ssl: bool = False
    read_from_replicas: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.startup_nodes, list):
            object.__setattr__(self, "startup_nodes", tuple(tuple(s) for s in self.startup_nodes))
