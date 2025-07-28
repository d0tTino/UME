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
            "event_type": "CREATE_NODE",
            "timestamp": 1,
            "node_id": "n1",
            "payload": {"node_id": "n1"},
        },
        {
            "event_type": "CREATE_NODE",
            "timestamp": 1,
            "node_id": "n2",
            "payload": {"node_id": "n2"},
        },
        {
            "event_type": "CREATE_EDGE",
            "timestamp": 1,
            "node_id": "n1",
            "target_node_id": "n2",
            "label": "RELATES_TO",
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
    assert ("n1", "n2", "RELATES_TO") in graph.get_all_edges()
    assert ledger.last_processed_offset == 2
