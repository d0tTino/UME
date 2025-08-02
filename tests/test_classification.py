import ume.services.ingest as ingest_module
from ume.graph import MockGraph
from ume.services import ingest_event
from ume.processing import apply_event_to_graph


def test_ingest_event_classifies_and_persists_tags(monkeypatch) -> None:
    graph = MockGraph()
    captured: dict[str, object] = {}

    def fake_apply_event(event, g):
        captured["event"] = event
        apply_event_to_graph(event, g)

    monkeypatch.setattr(ingest_module, "apply_event", fake_apply_event)

    data = {
        "event_type": "CREATE_NODE",
        "timestamp": 0,
        "node_id": "node1",
        "payload": {
            "node_id": "node1",
            "attributes": {"content": "This text mentions malware."},
        },
    }

    ingest_event(data, graph)

    stored = graph.get_node("node1")
    assert stored["tags"] == ["malware"]
    assert stored["tag_confidence"] == [1.0]

    event = captured["event"]
    assert event.payload["classification"] == [
        {"tag": "malware", "confidence": 1.0}
    ]
