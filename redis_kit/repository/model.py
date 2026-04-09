from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class BaseModel:
    """Base entity with audit metadata, versioning, and soft delete support."""

    id: str = ""
    version: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted: bool = False
    deleted_at: datetime | None = None
