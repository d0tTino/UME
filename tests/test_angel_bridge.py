import importlib.util
import sys
from pathlib import Path
import pytest
import time
from ume.event_ledger import EventLedger

module_path = Path(__file__).resolve().parents[1] / "src" / "ume" / "angel_bridge.py"
spec = importlib.util.spec_from_file_location("ume.angel_bridge", module_path)
assert spec and spec.loader
angel_bridge = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = angel_bridge
spec.loader.exec_module(angel_bridge)

AngelBridge = angel_bridge.AngelBridge  # type: ignore[attr-defined]
settings = angel_bridge.settings


def test_summary_generation() -> None:
    bridge = AngelBridge(lookback_hours=1)
    bridge.consume_events = lambda: [
        {"event_type": "CREATE_NODE", "timestamp": 1},
        {"event_type": "CREATE_EDGE", "timestamp": 1},
        {"event_type": "CREATE_NODE", "timestamp": 1},
    ]  # type: ignore[assignment]
    summary = bridge.emit_daily_summary()
    assert "CREATE_NODE: 2" in summary
    assert "CREATE_EDGE: 1" in summary


def test_consume_events_filters_by_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger_path = tmp_path / "ledger.db"
    ledger = EventLedger(str(ledger_path))
    monkeypatch.setattr(angel_bridge, "event_ledger", ledger)

    now = int(time.time())
    ledger.append(0, {"event_type": "CREATE_NODE", "timestamp": now, "node_id": "recent", "payload": {}})
    ledger.append(1, {"event_type": "CREATE_NODE", "timestamp": now - 5 * 3600, "node_id": "old", "payload": {}})

    monkeypatch.setattr(settings, "KAFKA_BOOTSTRAP_SERVERS", "", raising=False)
    bridge = AngelBridge(lookback_hours=2)
    events = bridge.consume_events()

    ids = {e["node_id"] for e in events}

    assert "recent" in ids
    assert "old" not in ids


def test_kafka_fallback_to_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Bridge should fall back to the ledger when Kafka raises an error."""

    class BrokenClient:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def __enter__(self) -> "BrokenClient":
            return self

        def __exit__(self, exc_type: type | None, exc: BaseException | None, tb: object) -> None:
            pass

        def consume_events(self, timeout: float = 0.5):
            raise RuntimeError("boom")

    ledger_path = tmp_path / "ledger.db"
    ledger = EventLedger(str(ledger_path))
    ledger.append(0, {"event_type": "CREATE_NODE", "timestamp": int(time.time()), "node_id": "foo", "payload": {}})

    monkeypatch.setattr(angel_bridge, "event_ledger", ledger)
    monkeypatch.setattr(angel_bridge, "UMEClient", BrokenClient)
    monkeypatch.setattr(settings, "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    bridge = AngelBridge(lookback_hours=2)
    events = bridge.consume_events()

    assert len(events) == 1
    assert events[0]["node_id"] == "foo"

