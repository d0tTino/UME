from ume.event import EventType
from ume.graph import MockGraph
from ume.services import ingest as ingest_module


def test_ingest_emits_anomaly_event(monkeypatch):
    events: list[str] = []

    def fake_apply_event(event, graph):
        events.append(event.event_type)

    monkeypatch.setattr(ingest_module, "apply_event", fake_apply_event)

    graph = MockGraph()

    data1 = {
        "eventType": EventType.CREATE_NODE.value,
        "timestamp": 0,
        "node_id": "n1",
        "payload": {"node_id": "n1", "attributes": {"name": "malware incident"}},
        "sourceService": "user1",
    }
    ingest_module.ingest_event(data1, graph)

    data2 = {
        "eventType": EventType.CREATE_NODE.value,
        "timestamp": 1,
        "node_id": "n2",
        "payload": {"node_id": "n2", "attributes": {"name": "phishing attempt"}},
        "sourceService": "user1",
    }
    ingest_module.ingest_event(data2, graph)

    assert EventType.ANOMALY_DETECTED.value in events
