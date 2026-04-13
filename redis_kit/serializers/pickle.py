from __future__ import annotations

import logging
import pickle
import threading
from typing import Any

from redis_kit.exceptions import SerializationError

_logger = logging.getLogger("redis_kit.serializers")
_pickle_warned = False
_pickle_warned_lock = threading.Lock()


class PickleSerializer:
    """Pickle serializer.

    .. warning::

        Pickle can execute arbitrary code during deserialization.
        Only use this serializer when **all** data in Redis is produced
        by trusted sources.  Never deserialize data from untrusted clients.
    """

    def __init__(self, protocol: int = pickle.HIGHEST_PROTOCOL) -> None:
        self._protocol = protocol
        global _pickle_warned  # noqa: PLW0603
        if not _pickle_warned:
            with _pickle_warned_lock:
                if not _pickle_warned:
                    _pickle_warned = True
                    _logger.warning(
                        "PickleSerializer is in use. Deserializing untrusted data with pickle "
                        "can execute arbitrary code. Only use in trusted environments."
                    )

    def dumps(self, value: Any) -> bytes:
        try:
            return pickle.dumps(value, protocol=self._protocol)
        except (pickle.PicklingError, TypeError, AttributeError) as e:
            raise SerializationError(f"Pickle serialization failed: {e}") from e

    def loads(self, data: bytes) -> Any:
        try:
            return pickle.loads(data)  # noqa: S301
        except (pickle.UnpicklingError, TypeError, EOFError) as e:
            raise SerializationError(f"Pickle deserialization failed: {e}") from e
