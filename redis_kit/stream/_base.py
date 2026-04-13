from __future__ import annotations

from typing import Any


class StreamProducerBase:
    """Shared logic for sync and async StreamProducer."""

    def __init__(
        self,
        client: Any,
        stream: str,
        prefix: str = "",
        maxlen: int | None = None,
    ) -> None:
        self._client = client
        self._stream = f"{prefix}:{stream}" if prefix else stream
        self._maxlen = maxlen


class StreamConsumerBase:
    """Shared logic for sync and async StreamConsumer."""

    def __init__(
        self,
        client: Any,
        stream: str,
        group: str,
        consumer_name: str,
        prefix: str = "",
        auto_ack: bool = True,
    ) -> None:
        self._client = client
        self._stream = f"{prefix}:{stream}" if prefix else stream
        self._group = group
        self._consumer_name = consumer_name
        self._auto_ack = auto_ack

    @staticmethod
    def _parse_autoclaim_messages(messages_data: list, stream: str, consumer: Any) -> list:
        """Parse xautoclaim message tuples into StreamMessage objects."""
        from redis_kit.stream.message import StreamMessage, decode_stream_data

        return [
            StreamMessage(
                id=msg_id.decode() if isinstance(msg_id, bytes) else msg_id,
                data=decode_stream_data(data),
                stream=stream,
                _consumer=consumer,
            )
            for msg_id, data in messages_data
        ]

    @staticmethod
    def _parse_pending_entries(result: list[dict]) -> list[dict]:
        return [
            {
                "id": (entry["message_id"].decode() if isinstance(entry["message_id"], bytes) else entry["message_id"]),
                "consumer": (entry["consumer"].decode() if isinstance(entry["consumer"], bytes) else entry["consumer"]),
                "idle_ms": entry["time_since_delivered"],
                "delivery_count": entry["times_delivered"],
            }
            for entry in result
        ]
