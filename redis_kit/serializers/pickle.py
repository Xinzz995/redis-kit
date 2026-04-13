from __future__ import annotations

import logging
import pickle
import threading
from typing import Any

from redis_kit.serializers.base import wrap_serialization

_logger = logging.getLogger("redis_kit.serializers")
_pickle_warned = False
_pickle_warned_lock = threading.Lock()

_DUMP_ERRORS = (pickle.PicklingError, TypeError, AttributeError)
_LOAD_ERRORS = (pickle.UnpicklingError, TypeError, EOFError)


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
        return wrap_serialization(
            lambda: pickle.dumps(value, protocol=self._protocol),
            _DUMP_ERRORS,
            "Pickle serialization failed",
        )

    def loads(self, data: bytes) -> Any:
        return wrap_serialization(
            lambda: pickle.loads(data),  # noqa: S301
            _LOAD_ERRORS,
            "Pickle deserialization failed",
        )
