from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis.asyncio


class AsyncStreamProducer:
    """Async producer for Redis Streams."""

    def __init__(
        self,
        client: redis.asyncio.Redis,
        stream: str,
        prefix: str = "",
        maxlen: int | None = None,
    ) -> None:
        self._client = client
        self._stream = f"{prefix}:{stream}" if prefix else stream
        self._maxlen = maxlen

    async def add(self, data: dict[str, str], msg_id: str = "*") -> str:
        result = await self._client.xadd(
            self._stream, data, id=msg_id,
            maxlen=self._maxlen, approximate=True if self._maxlen else False,
        )
        return result if isinstance(result, str) else result.decode()

    async def len(self) -> int:
        return await self._client.xlen(self._stream)

    async def trim(self, maxlen: int, approximate: bool = True) -> int:
        return await self._client.xtrim(self._stream, maxlen=maxlen, approximate=approximate)
