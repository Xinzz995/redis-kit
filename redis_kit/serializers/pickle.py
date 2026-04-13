from __future__ import annotations

import logging
import pickle
from typing import Any

_logger = logging.getLogger("redis_kit.serializers")


class PickleSerializer:
    """Pickle serializer.

    .. warning::

        Pickle can execute arbitrary code during deserialization.
        Only use this serializer when **all** data in Redis is produced
        by trusted sources.  Never deserialize data from untrusted clients.
    """

    def __init__(self, protocol: int = pickle.HIGHEST_PROTOCOL) -> None:
        self._protocol = protocol
        _logger.warning(
            "PickleSerializer is in use. Deserializing untrusted data with pickle "
            "can execute arbitrary code. Only use in trusted environments."
        )

    def dumps(self, value: Any) -> bytes:
        return pickle.dumps(value, protocol=self._protocol)

    def loads(self, data: bytes) -> Any:
        return pickle.loads(data)  # noqa: S301
