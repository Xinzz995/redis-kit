from __future__ import annotations

from redis_kit.stream._base import StreamProducerBase


class AsyncStreamProducer(StreamProducerBase):
    """Async producer for Redis Streams."""

    async def add(self, data: dict[str, str], msg_id: str = "*") -> str:
        result = await self._client.xadd(
            self._stream,
            data,
            id=msg_id,
            maxlen=self._maxlen,
            approximate=self._maxlen is not None,
        )
        return result if isinstance(result, str) else result.decode()

    async def len(self) -> int:
        return await self._client.xlen(self._stream)

    async def trim(self, maxlen: int, approximate: bool = True) -> int:
        return await self._client.xtrim(self._stream, maxlen=maxlen, approximate=approximate)
