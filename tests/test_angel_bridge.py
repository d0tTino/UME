import importlib.util
import sys
from pathlib import Path
import pytest
import time

module_path = Path(__file__).resolve().parents[1] / "src" / "ume" / "angel_bridge.py"
spec = importlib.util.spec_from_file_location("ume.angel_bridge", module_path)
assert spec and spec.loader
angel_bridge = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = angel_bridge
spec.loader.exec_module(angel_bridge)

AngelBridge = angel_bridge.AngelBridge  # type: ignore[attr-defined]
PersistentGraph = angel_bridge.PersistentGraph  # type: ignore[attr-defined]
settings = angel_bridge.settings


def test_summary_generation() -> None:
    bridge = AngelBridge(lookback_hours=1)
    bridge.consume_events = lambda: [{"foo": 1}, {"foo": 2}]  # type: ignore[assignment]
    summary = bridge.emit_daily_summary()
    assert "2 events" in summary


def test_consume_events_filters_by_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "graph.db"
    monkeypatch.setattr(settings, "UME_DB_PATH", str(db_path))

    graph = PersistentGraph(str(db_path))
    now = int(time.time())
    graph.add_node("recent", {})
    graph.add_node("old", {})
    graph.add_edge("recent", "recent", "new")
    graph.add_edge("recent", "old", "old")

    old_ts = now - 5 * 3600
    with graph.conn:
        graph.conn.execute("UPDATE nodes SET created_at=? WHERE id='old'", (old_ts,))
        graph.conn.execute("UPDATE edges SET created_at=? WHERE label='old'", (old_ts,))

    bridge = AngelBridge(lookback_hours=2)
    events = bridge.consume_events()

    node_ids = {e["id"] for e in events if e["type"] == "node"}
    edge_labels = {e["label"] for e in events if e["type"] == "edge"}

    assert "recent" in node_ids
    assert "old" not in node_ids
    assert "new" in edge_labels
    assert "old" not in edge_labels

