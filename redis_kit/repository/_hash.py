from __future__ import annotations

import dataclasses
import functools
import logging
import types
import typing
from datetime import datetime
from typing import TypeVar

from redis_kit.exceptions import RepositoryError
from redis_kit.repository.model import BaseModel

logger = logging.getLogger("redis_kit")

T = TypeVar("T", bound=BaseModel)


@functools.lru_cache(maxsize=64)
def _get_type_hints(model_class: type) -> dict[str, type]:
    """Cached version of typing.get_type_hints for model classes."""
    try:
        return typing.get_type_hints(model_class)
    except (NameError, AttributeError) as exc:
        logger.warning("Failed to resolve type hints for %s: %s", model_class.__name__, exc)
        return {}


def to_hash(entity: BaseModel) -> dict[str, str]:
    """Convert a BaseModel entity to a Redis hash mapping."""
    result = {}
    for f in dataclasses.fields(entity):
        value = getattr(entity, f.name)
        if value is None:
            result[f.name] = "__NONE__"
        elif isinstance(value, bool):
            result[f.name] = "1" if value else "0"
        elif isinstance(value, datetime):
            result[f.name] = value.isoformat()
        else:
            result[f.name] = str(value)
    return result


def from_hash(data: dict[bytes | str, bytes | str], model_class: type[T]) -> T:
    """Convert a Redis hash mapping back to a BaseModel entity."""
    decoded = {}
    for k, v in data.items():
        key = k.decode() if isinstance(k, bytes) else k
        val = v.decode() if isinstance(v, bytes) else v
        decoded[key] = val

    hints = _get_type_hints(model_class)

    kwargs = {}
    for f in dataclasses.fields(model_class):
        raw = decoded.get(f.name)
        ftype = hints.get(f.name, f.type)
        # Unwrap Optional/Union (e.g. int | None -> int)
        origin = typing.get_origin(ftype)
        if origin is types.UnionType or origin is typing.Union:
            args = [a for a in typing.get_args(ftype) if a is not type(None)]
            ftype = args[0] if args else ftype

        if raw is None or raw == "__NONE__":
            if raw == "__NONE__":
                kwargs[f.name] = None
            elif f.default is not dataclasses.MISSING:
                kwargs[f.name] = f.default
            elif f.default_factory is not dataclasses.MISSING:
                kwargs[f.name] = f.default_factory()
            else:
                raise RepositoryError(f"Field '{f.name}' is missing from the hash and has no default value")
        elif ftype is int:
            kwargs[f.name] = int(raw)
        elif ftype is float:
            kwargs[f.name] = float(raw)
        elif ftype is bool:
            kwargs[f.name] = raw == "1"
        elif ftype is datetime:
            kwargs[f.name] = datetime.fromisoformat(raw)
        else:
            kwargs[f.name] = raw
    return model_class(**kwargs)
