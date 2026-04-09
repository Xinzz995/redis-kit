from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from redis_kit.exceptions import StreamError


@dataclass
class StreamMessage:
    """A message from a Redis Stream."""

    id: str
    data: dict[str, str]
    stream: str
    _consumer: Any = field(default=None, repr=False)

    def ack(self) -> None:
        if self._consumer is None:
            raise StreamError("Cannot ack: message not associated with a consumer")
        self._consumer._ack(self.id)
