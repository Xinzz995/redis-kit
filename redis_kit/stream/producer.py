from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis


class StreamProducer:
    """Produces messages to a Redis Stream."""

    def __init__(
        self,
        client: redis.Redis,
        stream: str,
        prefix: str = "",
        maxlen: int | None = None,
    ) -> None:
        self._client = client
        self._stream = f"{prefix}:{stream}" if prefix else stream
        self._maxlen = maxlen

    def add(self, data: dict[str, str], msg_id: str = "*") -> str:
        result = self._client.xadd(
            self._stream,
            data,
            id=msg_id,
            maxlen=self._maxlen,
            approximate=True if self._maxlen else False,
        )
        return result if isinstance(result, str) else result.decode()

    def len(self) -> int:
        return self._client.xlen(self._stream)

    def trim(self, maxlen: int, approximate: bool = True) -> int:
        return self._client.xtrim(self._stream, maxlen=maxlen, approximate=approximate)
