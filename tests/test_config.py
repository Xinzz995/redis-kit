from redis_kit.config import ConnectionConfig, NamespaceConfig


class TestConnectionConfig:
    def test_defaults(self):
        config = ConnectionConfig()
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.password is None
        assert config.max_connections == 10
        assert config.socket_timeout == 5.0
        assert config.socket_connect_timeout == 5.0
        assert config.decode_responses is False
        assert config.ssl is False
        assert config.url is None

    def test_url_takes_precedence(self):
        config = ConnectionConfig(url="redis://myhost:6380/2")
        assert config.url == "redis://myhost:6380/2"

    def test_frozen(self):
        config = ConnectionConfig()
        import pytest
        with pytest.raises(AttributeError):
            config.host = "other"  # type: ignore[misc]

    def test_custom_values(self):
        config = ConnectionConfig(
            host="redis.example.com",
            port=6380,
            db=5,
            password="secret",
            max_connections=50,
            ssl=True,
        )
        assert config.host == "redis.example.com"
        assert config.port == 6380
        assert config.db == 5
        assert config.password == "secret"
        assert config.max_connections == 50
        assert config.ssl is True


class TestNamespaceConfig:
    def test_defaults(self):
        ns = NamespaceConfig()
        assert ns.prefix == ""
        assert ns.separator == ":"

    def test_custom(self):
        ns = NamespaceConfig(prefix="myapp", separator="::")
        assert ns.prefix == "myapp"
        assert ns.separator == "::"

    def test_build_key_no_prefix(self):
        ns = NamespaceConfig()
        assert ns.build_key("user", "123") == "user:123"

    def test_build_key_with_prefix(self):
        ns = NamespaceConfig(prefix="myapp")
        assert ns.build_key("user", "123") == "myapp:user:123"

    def test_build_key_single_part(self):
        ns = NamespaceConfig(prefix="app")
        assert ns.build_key("key") == "app:key"

    def test_frozen(self):
        ns = NamespaceConfig()
        import pytest
        with pytest.raises(AttributeError):
            ns.prefix = "other"  # type: ignore[misc]
