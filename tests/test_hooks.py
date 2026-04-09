from redis_kit.hooks import CommandHook, CompositeHook


class RecordingHook:
    """Test hook that records calls."""

    def __init__(self):
        self.calls: list[tuple] = []

    def before(self, command: str, key: str, args: tuple) -> None:
        self.calls.append(("before", command, key, args))

    def after(self, command: str, key: str, result, duration_ms: float) -> None:
        self.calls.append(("after", command, key, result, duration_ms))

    def on_error(self, command: str, key: str, error: Exception) -> None:
        self.calls.append(("on_error", command, key, str(error)))


class TestCommandHookProtocol:
    def test_recording_hook_conforms(self):
        hook = RecordingHook()
        assert isinstance(hook, CommandHook)

    def test_recording_hook_before(self):
        hook = RecordingHook()
        hook.before("GET", "mykey", ())
        assert hook.calls == [("before", "GET", "mykey", ())]

    def test_recording_hook_after(self):
        hook = RecordingHook()
        hook.after("GET", "mykey", "value", 1.5)
        assert hook.calls == [("after", "GET", "mykey", "value", 1.5)]

    def test_recording_hook_on_error(self):
        hook = RecordingHook()
        hook.on_error("SET", "mykey", ValueError("bad"))
        assert hook.calls[0][:3] == ("on_error", "SET", "mykey")


class TestCompositeHook:
    def test_chains_before(self):
        h1, h2 = RecordingHook(), RecordingHook()
        composite = CompositeHook(h1, h2)
        composite.before("GET", "k", ())
        assert len(h1.calls) == 1
        assert len(h2.calls) == 1

    def test_chains_after(self):
        h1, h2 = RecordingHook(), RecordingHook()
        composite = CompositeHook(h1, h2)
        composite.after("GET", "k", "v", 1.0)
        assert len(h1.calls) == 1
        assert len(h2.calls) == 1

    def test_chains_on_error(self):
        h1, h2 = RecordingHook(), RecordingHook()
        composite = CompositeHook(h1, h2)
        composite.on_error("GET", "k", RuntimeError("fail"))
        assert len(h1.calls) == 1
        assert len(h2.calls) == 1

    def test_empty_composite(self):
        composite = CompositeHook()
        composite.before("GET", "k", ())  # Should not raise

    def test_conforms_to_protocol(self):
        assert isinstance(CompositeHook(), CommandHook)
