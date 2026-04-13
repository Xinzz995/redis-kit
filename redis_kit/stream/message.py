from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from redis_kit.exceptions import StreamError

if TYPE_CHECKING:
    from redis_kit.stream.async_consumer import AsyncStreamConsumer
    from redis_kit.stream.consumer import StreamConsumer


def decode_stream_data(data: dict[bytes | str, bytes | str]) -> dict[str, str]:
    """Decode bytes keys/values from Redis stream data to strings."""
    return {
        (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
        for k, v in data.items()
    }


@dataclass
class StreamMessage:
    """A message from a Redis Stream."""

    id: str
    data: dict[str, str]
    stream: str
    _consumer: StreamConsumer | AsyncStreamConsumer | None = field(default=None, repr=False)

    def ack(self) -> None:
        if self._consumer is None:
            raise StreamError("Cannot ack: message not associated with a consumer")
        self._consumer._ack(self.id)

    async def async_ack(self) -> None:
        if self._consumer is None:
            raise StreamError("Cannot ack: message not associated with a consumer")
        async_ack = getattr(self._consumer, "_async_ack", None)
        if async_ack is None:
            raise StreamError("Use 'message.ack()' with sync consumers. StreamMessage.async_ack() is async-only.")
        await async_ack(self.id)
