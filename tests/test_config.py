from redis_kit.config import ClusterConfig, ConnectionConfig, NamespaceConfig, SentinelConfig


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


class TestSentinelConfig:
    def test_required_fields(self):
        config = SentinelConfig(
            sentinels=[("sentinel1", 26379), ("sentinel2", 26379)],
            service_name="mymaster",
        )
        assert config.sentinels == (("sentinel1", 26379), ("sentinel2", 26379))
        assert config.service_name == "mymaster"

    def test_defaults(self):
        config = SentinelConfig(sentinels=[("h", 26379)], service_name="m")
        assert config.db == 0
        assert config.password is None
        assert config.sentinel_password is None
        assert config.max_connections == 10
        assert config.socket_timeout == 5.0
        assert config.socket_connect_timeout == 5.0
        assert config.decode_responses is False
        assert config.ssl is False

    def test_frozen(self):
        import pytest

        config = SentinelConfig(sentinels=[("h", 26379)], service_name="m")
        with pytest.raises(AttributeError):
            config.service_name = "other"

    def test_custom_values(self):
        config = SentinelConfig(
            sentinels=[("s1", 26379), ("s2", 26380), ("s3", 26381)],
            service_name="mymaster",
            db=3,
            password="redis_pass",
            sentinel_password="sentinel_pass",
            max_connections=50,
            ssl=True,
        )
        assert len(config.sentinels) == 3
        assert config.password == "redis_pass"
        assert config.sentinel_password == "sentinel_pass"

    def test_list_auto_converts_to_tuple(self):
        config = SentinelConfig(sentinels=[("host1", 26379)], service_name="mymaster")
        assert isinstance(config.sentinels, tuple)
        assert isinstance(config.sentinels[0], tuple)

    def test_tuple_input_preserved(self):
        config = SentinelConfig(
            sentinels=(("host1", 26379), ("host2", 26379)),
            service_name="mymaster",
        )
        assert isinstance(config.sentinels, tuple)
        assert config.sentinels == (("host1", 26379), ("host2", 26379))


class TestClusterConfig:
    def test_required_fields(self):
        config = ClusterConfig(startup_nodes=[("node1", 6379), ("node2", 6380)])
        assert config.startup_nodes == (("node1", 6379), ("node2", 6380))

    def test_defaults(self):
        config = ClusterConfig(startup_nodes=[("h", 6379)])
        assert config.password is None
        assert config.max_connections == 10
        assert config.socket_timeout == 5.0
        assert config.decode_responses is False
        assert config.ssl is False
        assert config.read_from_replicas is False

    def test_frozen(self):
        import pytest

        config = ClusterConfig(startup_nodes=[("h", 6379)])
        with pytest.raises(AttributeError):
            config.password = "x"

    def test_custom_values(self):
        config = ClusterConfig(
            startup_nodes=[("n1", 6379), ("n2", 6380), ("n3", 6381)],
            password="secret",
            max_connections=50,
            read_from_replicas=True,
            ssl=True,
        )
        assert len(config.startup_nodes) == 3
        assert config.read_from_replicas is True

    def test_list_auto_converts_to_tuple(self):
        config = ClusterConfig(startup_nodes=[("host1", 7000)])
        assert isinstance(config.startup_nodes, tuple)
        assert isinstance(config.startup_nodes[0], tuple)

    def test_tuple_input_preserved(self):
        config = ClusterConfig(
            startup_nodes=(("host1", 7000), ("host2", 7001)),
        )
        assert isinstance(config.startup_nodes, tuple)
        assert config.startup_nodes == (("host1", 7000), ("host2", 7001))
