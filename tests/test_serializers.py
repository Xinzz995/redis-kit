import logging

import pytest

from redis_kit.serializers import JsonSerializer, PickleSerializer
from redis_kit.serializers.base import Serializer


class TestJsonSerializer:
    def setup_method(self):
        self.s = JsonSerializer()

    def test_roundtrip_dict(self):
        data = {"name": "Alice", "age": 30}
        assert self.s.loads(self.s.dumps(data)) == data

    def test_roundtrip_list(self):
        data = [1, 2, 3]
        assert self.s.loads(self.s.dumps(data)) == data

    def test_roundtrip_string(self):
        assert self.s.loads(self.s.dumps("hello")) == "hello"

    def test_roundtrip_number(self):
        assert self.s.loads(self.s.dumps(42)) == 42
        assert self.s.loads(self.s.dumps(3.14)) == pytest.approx(3.14)

    def test_roundtrip_none(self):
        assert self.s.loads(self.s.dumps(None)) is None

    def test_roundtrip_bool(self):
        assert self.s.loads(self.s.dumps(True)) is True

    def test_dumps_returns_bytes(self):
        result = self.s.dumps({"key": "value"})
        assert isinstance(result, bytes)

    def test_loads_accepts_bytes(self):
        result = self.s.loads(b'{"key": "value"}')
        assert result == {"key": "value"}

    def test_conforms_to_protocol(self):
        assert isinstance(self.s, Serializer)


class TestPickleSerializer:
    def setup_method(self):
        self.s = PickleSerializer()

    def test_roundtrip_dict(self):
        data = {"name": "Alice", "items": [1, 2, 3]}
        assert self.s.loads(self.s.dumps(data)) == data

    def test_roundtrip_complex_object(self):
        data = {"set": {1, 2, 3}, "tuple": (1, 2)}
        result = self.s.loads(self.s.dumps(data))
        assert result["set"] == {1, 2, 3}
        assert result["tuple"] == (1, 2)

    def test_dumps_returns_bytes(self):
        assert isinstance(self.s.dumps("hello"), bytes)

    def test_conforms_to_protocol(self):
        assert isinstance(self.s, Serializer)


def test_pickle_serializer_emits_security_warning(caplog):
    """PickleSerializer should log a security warning on first instantiation."""
    from redis_kit.serializers.pickle import PickleSerializer

    PickleSerializer._warned = False  # reset for test isolation
    with caplog.at_level(logging.WARNING, logger="redis_kit.serializers"):
        PickleSerializer()
    assert any("pickle" in r.message.lower() and "untrusted" in r.message.lower() for r in caplog.records)
    # Second instantiation should NOT warn again
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="redis_kit.serializers"):
        PickleSerializer()
    assert not any("pickle" in r.message.lower() for r in caplog.records)


class TestMsgpackSerializer:
    def test_roundtrip(self):
        msgpack = pytest.importorskip("msgpack")  # noqa: F841
        from redis_kit.serializers import MsgpackSerializer

        s = MsgpackSerializer()
        data = {"name": "Alice", "age": 30}
        assert s.loads(s.dumps(data)) == data

    def test_dumps_returns_bytes(self):
        pytest.importorskip("msgpack")
        from redis_kit.serializers import MsgpackSerializer

        s = MsgpackSerializer()
        assert isinstance(s.dumps("hello"), bytes)

    def test_conforms_to_protocol(self):
        pytest.importorskip("msgpack")
        from redis_kit.serializers import MsgpackSerializer

        assert isinstance(MsgpackSerializer(), Serializer)
