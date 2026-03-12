import json

from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume.config import settings
from ume.event_ledger import EventLedger
from ume.graph import MockGraph
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

    def poll(self, timeout: float = 1.0):
        if self.index >= len(self.messages):
            raise KeyboardInterrupt
        msg = self.messages[self.index]
        self.index += 1
        return msg

    def close(self) -> None:
        return None


def _token(client: TestClient) -> str:
    response = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    )
    return response.json()["access_token"]


def test_golden_path_api_and_kafka_are_equivalent(tmp_path, monkeypatch):
    events = [
        {
            "eventType": "CREATE_NODE",
            "eventId": "g-1",
            "timestamp": 1,
            "node_id": "n1",
            "payload": {"node_id": "n1", "attributes": {"name": "Alice"}},
        },
        {
            "eventType": "CREATE_NODE",
            "eventId": "g-2",
            "timestamp": 2,
            "node_id": "n2",
            "payload": {"node_id": "n2", "attributes": {"name": "Bob"}},
        },
        {
            "eventType": "CREATE_EDGE",
            "eventId": "g-3",
            "timestamp": 3,
            "node_id": "n1",
            "target_node_id": "n2",
            "label": "KNOWS",
            "payload": {},
        },
    ]

    api_graph = MockGraph()
    configure_graph(api_graph)
    client = TestClient(app)
    response = client.post(
        "/events/batch",
        json=events,
        headers={"Authorization": f"Bearer {_token(client)}"},
    )
    assert response.status_code == 200

    kafka_graph = MockGraph()
    ledger = EventLedger(str(tmp_path / "ledger.db"))
    consumer = DummyConsumer(
        [DummyMessage(json.dumps(event).encode("utf-8"), idx) for idx, event in enumerate(events)]
    )
    monkeypatch.setattr(graph_consumer, "event_ledger", ledger)

    graph_consumer.run_event_pipeline_consumer(kafka_graph, consumer=consumer)

    assert api_graph.dump() == kafka_graph.dump()
    assert ledger.last_processed_offset == len(events) - 1
    rejected = [item for _, item in ledger.range() if item.get("eventType") == "REJECTED_EVENT"]
    assert rejected == []
