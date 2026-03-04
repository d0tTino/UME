from ume.event_ledger import EventLedger
from ume.persistent_graph import PersistentGraph
from ume.replay import replay_from_ledger, build_graph_from_ledger
from ume.graph_schema import EdgeLabel, GraphSchema
from ume.schema_manager import DEFAULT_SCHEMA_MANAGER
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


def test_build_graph_from_ledger_roundtrip(tmp_path):
    ledger = EventLedger(str(tmp_path / "ledger.db"))
    ledger.append(
        0,
        {
            "event_type": "CREATE_NODE",
            "timestamp": 1,
            "node_id": "a",
            "payload": {"node_id": "a"},
        },
    )
    ledger.append(
        1,
        {
            "event_type": "CREATE_NODE",
            "timestamp": 2,
            "node_id": "b",
            "payload": {"node_id": "b"},
        },
    )
    ledger.append(
        2,
        {
            "event_type": "CREATE_EDGE",
            "timestamp": 3,
            "node_id": "a",
            "target_node_id": "b",
            "label": "TAGGED_AS",
            "payload": {},
        },
    )

    graph = build_graph_from_ledger(ledger)
    assert set(graph.get_all_node_ids()) == {"a", "b"}
    assert ("a", "b", "TAGGED_AS", {"schema_version": "3.0.0"}) in graph.get_all_edges()


def test_replay_mixed_schema_versions_use_event_schema(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    ledger = EventLedger(str(tmp_path / "ledger.db"))

    schema_v1 = GraphSchema(version="1.0.0", edge_labels={"TAGGED_AS": EdgeLabel("TAGGED_AS", "1.0.0")})
    schema_v2 = GraphSchema(version="2.0.0", edge_labels={"TAGGED_AS": EdgeLabel("TAGGED_AS", "2.0.0")})

    monkeypatch.setattr(
        DEFAULT_SCHEMA_MANAGER,
        "get_schema",
        lambda version=None: schema_v2 if version == "2.0.0" else schema_v1,
    )

    ledger.append(0, {"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "a", "payload": {"node_id": "a"}})
    ledger.append(1, {"event_type": "CREATE_NODE", "timestamp": 2, "node_id": "b", "payload": {"node_id": "b"}})
    ledger.append(2, {"event_type": "CREATE_NODE", "timestamp": 3, "node_id": "c", "payload": {"node_id": "c"}})
    ledger.append(3, {
        "event_type": "CREATE_EDGE",
        "timestamp": 4,
        "node_id": "a",
        "target_node_id": "b",
        "label": "TAGGED_AS",
        "schema_version": "1.0.0",
        "payload": {},
    })
    ledger.append(4, {
        "event_type": "CREATE_EDGE",
        "timestamp": 5,
        "node_id": "a",
        "target_node_id": "c",
        "label": "TAGGED_AS",
        "schema_version": "2.0.0",
        "payload": {},
    })

    graph = PersistentGraph(":memory:")
    replay_from_ledger(graph, ledger, 0)

    attrs_by_target = {target: attrs for _src, target, _label, attrs in graph.get_all_edges()}
    assert attrs_by_target["b"]["schema_version"] == "1.0.0"
    assert attrs_by_target["c"]["schema_version"] == "2.0.0"
