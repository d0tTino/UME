from ume.event_ledger import EventLedger
from ume.persistent_graph import PersistentGraph


def test_replay_from_offset(tmp_path):
    ledger = EventLedger(str(tmp_path / "ledger.db"))
    event1 = {"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1", "payload": {"node_id": "n1"}}
    event2 = {"event_type": "CREATE_NODE", "timestamp": 2, "node_id": "n2", "payload": {"node_id": "n2"}}
    ledger.append(0, event1)
    ledger.append(1, event2)

    g = PersistentGraph(":memory:")
    last = g.replay_from_ledger(ledger, 0)
    assert g.get_node("n1") is not None
    assert g.get_node("n2") is not None
    assert last == 1

