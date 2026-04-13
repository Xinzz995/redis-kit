from __future__ import annotations

from collections.abc import AsyncIterator

from redis.exceptions import ResponseError

from redis_kit.exceptions import StreamError
from redis_kit.stream._base import StreamConsumerBase
from redis_kit.stream.message import StreamMessage, decode_stream_data


class AsyncStreamConsumer(StreamConsumerBase):
    """Async consumer for Redis Streams using consumer groups."""

    async def ensure_group(self, start_id: str = "0") -> None:
        try:
            await self._client.xgroup_create(self._stream, self._group, id=start_id, mkstream=True)
        except ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise StreamError(f"Failed to create group '{self._group}'") from e
        except Exception as e:
            raise StreamError(f"Failed to create group '{self._group}'") from e

    async def listen(self, count: int = 10, block: int = 5000) -> AsyncIterator[StreamMessage]:
        results = await self._client.xreadgroup(
            self._group,
            self._consumer_name,
            {self._stream: ">"},
            count=count,
            block=block,
        )
        if not results:
            return
        for stream_name, messages in results:
            s_name = stream_name.decode() if isinstance(stream_name, bytes) else stream_name
            for msg_id, data in messages:
                m_id = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
                msg = StreamMessage(id=m_id, data=decode_stream_data(data), stream=s_name, _consumer=self)
                yield msg
                if self._auto_ack:
                    await self._async_ack(m_id)

    async def _async_ack(self, msg_id: str) -> None:
        await self._client.xack(self._stream, self._group, msg_id)

    def _ack(self, msg_id: str) -> None:
        """Sync ack not supported for async consumer. Use message.async_ack() instead."""
        raise StreamError("Use 'await message.async_ack()' in async context. StreamMessage.ack() is sync-only.")

    async def pending(self, count: int = 10, min_idle_ms: int = 0) -> list[dict]:
        result = await self._client.xpending_range(
            self._stream,
            self._group,
            min="-",
            max="+",
            count=count,
            idle=min_idle_ms,
        )
        return self._parse_pending_entries(result)

    async def claim_stale(self, min_idle_ms: int = 60000, count: int = 10) -> list[StreamMessage]:
        result = await self._client.xautoclaim(
            self._stream,
            self._group,
            self._consumer_name,
            min_idle_time=min_idle_ms,
            start_id="0-0",
            count=count,
        )
        messages_data = result[1] if len(result) > 1 else []
        messages = []
        for msg_id, data in messages_data:
            m_id = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
            messages.append(StreamMessage(id=m_id, data=decode_stream_data(data), stream=self._stream, _consumer=self))
        return messages

    async def destroy_group(self) -> None:
        await self._client.xgroup_destroy(self._stream, self._group)
