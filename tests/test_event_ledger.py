from ume.event_ledger import EventLedger
from ume.persistent_graph import PersistentGraph
from ume.replay import replay_from_ledger
import pytest


def test_replay_from_offset(tmp_path):
    ledger = EventLedger(str(tmp_path / "ledger.db"))
    event1 = {"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1", "payload": {"node_id": "n1"}}
    event2 = {"event_type": "CREATE_NODE", "timestamp": 2, "node_id": "n2", "payload": {"node_id": "n2"}}
    ledger.append(0, event1)
    ledger.append(1, event2)

    g = PersistentGraph(":memory:")
    last = replay_from_ledger(g, ledger, 0)
    assert g.get_node("n1") is not None
    assert g.get_node("n2") is not None
    assert last == 1


def test_append_duplicate_offset_error(tmp_path):
    ledger = EventLedger(str(tmp_path / "ledger.db"))
    event1 = {
        "event_type": "CREATE_NODE",
        "timestamp": 1,
        "node_id": "n1",
        "payload": {"node_id": "n1"},
    }
    ledger.append(0, event1)

    with pytest.raises(ValueError):
        ledger.append(
            0,
            {
                "event_type": "CREATE_NODE",
                "timestamp": 2,
                "node_id": "n2",
                "payload": {"node_id": "n2"},
            },
        )

    # Existing event should remain unchanged
    events = ledger.range()
    assert len(events) == 1
    assert events[0][0] == 0
    assert events[0][1] == event1


def test_replay_from_timestamp(tmp_path):
    ledger = EventLedger(str(tmp_path / "ledger.db"))
    for i in range(5):
        ledger.append(
            i,
            {
                "event_type": "CREATE_NODE",
                "timestamp": i,
                "node_id": f"n{i}",
                "payload": {"node_id": f"n{i}"},
            },
        )

    # Replay up to timestamp 2
    g = PersistentGraph(":memory:")
    replay_from_ledger(g, ledger, 0, end_timestamp=2)
    assert set(g.get_all_node_ids()) == {"n0", "n1", "n2"}

    # Replay up to timestamp 4

    g2 = PersistentGraph(":memory:")
    replay_from_ledger(g2, ledger, 0, end_timestamp=4)
    assert set(g2.get_all_node_ids()) == {"n0", "n1", "n2", "n3", "n4"}

    ledger.close()


def test_update_bookmark_invalid(tmp_path):
    ledger = EventLedger(str(tmp_path / "ledger.db"))
    with pytest.raises(ValueError):
        ledger.update_bookmark(-1)


def test_compact_removes_old_events(tmp_path):
    ledger = EventLedger(str(tmp_path / "ledger.db"))
    for i in range(5):
        ledger.append(i, {"val": i})

    ledger.compact(3)

    remaining = ledger.range()
    assert [off for off, _ in remaining] == [3, 4]


def test_bookmark_persists_between_instances(tmp_path):
    path = str(tmp_path / "ledger.db")
    ledger = EventLedger(path)
    ledger.update_bookmark(2)
    ledger.close()

    ledger2 = EventLedger(path)
    assert ledger2.last_processed_offset == 2
    ledger2.update_bookmark(4)
    ledger2.close()

    ledger3 = EventLedger(path)
    assert ledger3.last_processed_offset == 4
