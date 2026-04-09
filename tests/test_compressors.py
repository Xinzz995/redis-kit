import pytest

from redis_kit.compressors import ZlibCompressor
from redis_kit.compressors.base import Compressor


class TestZlibCompressor:
    def setup_method(self):
        self.c = ZlibCompressor()

    def test_roundtrip(self):
        data = b"hello world" * 100
        compressed = self.c.compress(data)
        assert self.c.decompress(compressed) == data

    def test_compress_returns_bytes(self):
        assert isinstance(self.c.compress(b"data"), bytes)

    def test_compressed_is_smaller(self):
        data = b"hello world" * 1000
        assert len(self.c.compress(data)) < len(data)

    def test_conforms_to_protocol(self):
        assert isinstance(self.c, Compressor)


class TestZstdCompressor:
    def test_roundtrip(self):
        pytest.importorskip("zstandard")
        from redis_kit.compressors import ZstdCompressor

        c = ZstdCompressor()
        data = b"hello world" * 100
        assert c.decompress(c.compress(data)) == data

    def test_conforms_to_protocol(self):
        pytest.importorskip("zstandard")
        from redis_kit.compressors import ZstdCompressor

        assert isinstance(ZstdCompressor(), Compressor)


class TestLz4Compressor:
    def test_roundtrip(self):
        pytest.importorskip("lz4.frame")
        from redis_kit.compressors import Lz4Compressor

        c = Lz4Compressor()
        data = b"hello world" * 100
        assert c.decompress(c.compress(data)) == data

    def test_conforms_to_protocol(self):
        pytest.importorskip("lz4.frame")
        from redis_kit.compressors import Lz4Compressor

        assert isinstance(Lz4Compressor(), Compressor)
