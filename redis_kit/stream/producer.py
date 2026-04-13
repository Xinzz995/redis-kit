from __future__ import annotations

from redis_kit.stream._base import StreamProducerBase


class StreamProducer(StreamProducerBase):
    """Produces messages to a Redis Stream."""

    def add(self, data: dict[str, str], msg_id: str = "*") -> str:
        result = self._client.xadd(
            self._stream,
            data,
            id=msg_id,
            maxlen=self._maxlen,
            approximate=self._maxlen is not None,
        )
        return result if isinstance(result, str) else result.decode()

    def len(self) -> int:
        return self._client.xlen(self._stream)

    def trim(self, maxlen: int, approximate: bool = True) -> int:
        return self._client.xtrim(self._stream, maxlen=maxlen, approximate=approximate)
