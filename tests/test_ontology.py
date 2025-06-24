import time
from ume import Event, EventType, MockGraph, apply_event_to_graph
from ume import ontology


def test_build_concept_graph(monkeypatch):
    graph = MockGraph()
    now = int(time.time())
    events = [
        Event(
            event_type=EventType.CREATE_NODE,
            timestamp=now,
            payload={"node_id": "n1", "attributes": {"text": "apple fruit"}},
        ),
        Event(
            event_type=EventType.CREATE_NODE,
            timestamp=now,
            payload={"node_id": "n2", "attributes": {"text": "banana fruit"}},
        ),
        Event(
            event_type=EventType.CREATE_NODE,
            timestamp=now,
            payload={"node_id": "n3", "attributes": {"text": "car vehicle"}},
        ),
    ]
    for e in events:
        apply_event_to_graph(e, graph)

    def fake_embed(text: str):
        if "apple" in text:
            return [1.0, 0.0]
        if "banana" in text:
            return [0.9, 0.1]
        return [0.0, 1.0]

    monkeypatch.setattr(ontology, "generate_embedding", fake_embed)

    rel_events = ontology.build_concept_graph(graph, threshold=0.8)
    assert any(
        ev.node_id == "n1" and ev.target_node_id == "n2" for ev in rel_events
    )
    assert ("n1", "n2", "RELATES_TO") in graph.get_all_edges()
