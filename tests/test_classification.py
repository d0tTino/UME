import ume.services.ingest as ingest_module
from ume.graph import MockGraph
from ume.services import ingest_event
from ume.processing import apply_event_to_graph
from ume.event import Event
from ume.classification.service import classify_event


def test_ingest_event_classifies_and_persists_tags(monkeypatch) -> None:
    graph = MockGraph()
    captured: dict[str, object] = {}

    def fake_apply_event(event, g, *, schema_version: str | None = None):
        captured["event"] = event
        if schema_version is None:
            apply_event_to_graph(event, g)
        else:
            apply_event_to_graph(event, g, schema_version=schema_version)

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
        {
            "tag": "malware",
            "confidence": 1.0,
            "domain": None,
            "subdomain": None,
            "sensitivity": None,
        }
    ]


def test_finance_tag_generation(finance_engine_mock) -> None:
    event = Event(event_type="CREATE_NODE", timestamp=0, payload={"transaction": {"amount": 1}})
    results = classify_event(event)
    assert [r.tag for r in results] == ["finance:food"]


def test_research_tag_generation(tino_storm_mock) -> None:
    event = Event(
        event_type="CREATE_NODE",
        timestamp=0,
        payload={"attributes": {"content": "some text"}},
    )
    results = classify_event(event)
    assert [r.tag for r in results] == ["research:ml:low"]
    assert results[0].domain == "research"
