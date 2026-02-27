import json

import pytest

from ume import MockGraph
from ume.event_ledger import EventLedger
from ume.pipeline import graph_consumer


class DummyMessage:
    def __init__(self, value: bytes, offset: int) -> None:
        self._value = value
        self._offset = offset

    def value(self) -> bytes:
        return self._value

    def error(self):
        return None

    def offset(self) -> int:
        return self._offset


class DummyConsumer:
    def __init__(self, messages: list[DummyMessage]) -> None:
        self.messages = messages
        self.index = 0
        self.closed = False

    def subscribe(self, topics):
        self.topics = topics

    def poll(self, timeout: float = 1.0):
        if self.index >= len(self.messages):
            raise KeyboardInterrupt
        msg = self.messages[self.index]
        self.index += 1
        return msg

    def close(self) -> None:
        self.closed = True


def _patch_modules(monkeypatch: pytest.MonkeyPatch, consumer: DummyConsumer, ledger: EventLedger) -> None:
    monkeypatch.setattr(graph_consumer, "Consumer", lambda conf: consumer)
    monkeypatch.setattr(graph_consumer, "ssl_config", lambda: {})
    monkeypatch.setattr(graph_consumer, "event_ledger", ledger)


def test_graph_consumer_applies_events(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = EventLedger(str(tmp_path / "ledger.db"))
    events = [
        {
            "eventType": "CREATE_NODE",
            "eventId": "evt-1",
            "timestamp": 1,
            "nodeId": "n1",
            "payload": {"node_id": "n1"},
        },
        {
            "eventType": "CREATE_NODE",
            "eventId": "evt-2",
            "timestamp": 1,
            "nodeId": "n2",
            "payload": {"node_id": "n2"},
        },
        {
            "eventType": "CREATE_EDGE",
            "eventId": "evt-3",
            "timestamp": 1,
            "nodeId": "n1",
            "targetNodeId": "n2",
            "label": "TAGGED_AS",
            "payload": {},
        },
    ]
    msgs = [DummyMessage(json.dumps(e).encode("utf-8"), i) for i, e in enumerate(events)]
    consumer = DummyConsumer(msgs)
    _patch_modules(monkeypatch, consumer, ledger)

    graph = MockGraph()
    graph_consumer.run_graph_consumer(graph)

    assert graph.node_exists("n1")
    assert graph.node_exists("n2")
    assert ("n1", "n2", "TAGGED_AS", {"schema_version": "3.0.0"}) in graph.get_all_edges()
    assert ledger.last_processed_offset == 2


def test_graph_consumer_replay_is_deterministic_for_rejections(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events = [
        {
            "eventType": "CREATE_NODE",
            "eventId": "det-1",
            "timestamp": 1,
            "nodeId": "n1",
            "payload": {"node_id": "n1"},
        },
        {
            "eventType": "CREATE_EDGE",
            "eventId": "det-2",
            "timestamp": 1,
            "nodeId": "n1",
            "targetNodeId": "n2",
            "label": "UNKNOWN_LABEL",
            "payload": {},
        },
        {
            "eventType": "NOT_A_REAL_EVENT",
            "eventId": "det-3",
            "timestamp": 1,
            "payload": {},
        },
    ]

    def _run(db_name: str) -> tuple[dict, list[tuple[int, dict]]]:
        ledger = EventLedger(str(tmp_path / db_name))
        msgs = [DummyMessage(json.dumps(e).encode("utf-8"), i) for i, e in enumerate(events)]
        consumer = DummyConsumer(msgs)
        _patch_modules(monkeypatch, consumer, ledger)

        graph = MockGraph()
        graph_consumer.run_graph_consumer(graph)
        rejected = [item for item in ledger.range() if item[1].get("eventType") == "REJECTED_EVENT"]
        return graph.dump(), rejected

    state_a, rejected_a = _run("ledger_a.db")
    state_b, rejected_b = _run("ledger_b.db")

    assert state_a == state_b
    assert rejected_a == rejected_b
    assert len(rejected_a) == 2
