from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class BaseModel:
    """Base entity with audit metadata, versioning, and soft delete support.

    Entities are mutable dataclasses for ergonomic field updates. However,
    to preserve version integrity, always use ``dataclasses.replace()`` to
    create modified copies rather than mutating fields in place::

        updated = dataclasses.replace(entity, name="new name")
        repo.save(updated)
    """

    id: str = ""
    version: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted: bool = False
    deleted_at: datetime | None = None
