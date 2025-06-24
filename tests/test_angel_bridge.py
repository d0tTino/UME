from ume.angel_bridge import AngelBridge


class DummyBridge(AngelBridge):
    def consume_events(self):  # type: ignore[override]
        return [{"foo": 1}, {"foo": 2}]


def test_summary_generation() -> None:
    bridge = DummyBridge(lookback_hours=1)
    summary = bridge.emit_daily_summary()
    assert "2 events" in summary
