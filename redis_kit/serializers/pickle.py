from __future__ import annotations

import pickle
from typing import Any


class PickleSerializer:
    """Pickle serializer. Only use in trusted environments."""

    def __init__(self, protocol: int = pickle.HIGHEST_PROTOCOL) -> None:
        self._protocol = protocol

    def dumps(self, value: Any) -> bytes:
        return pickle.dumps(value, protocol=self._protocol)

    def loads(self, data: bytes) -> Any:
        return pickle.loads(data)  # noqa: S301
