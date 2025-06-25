import types
import sys
import time
import pytest

pytest.importorskip("sentence_transformers")


def test_listener_creates_edges(monkeypatch):
    embed_mod = sys.modules.setdefault("ume.embedding", types.ModuleType("ume.embedding"))
    monkeypatch.setattr(
        embed_mod,
        "generate_embedding",
        lambda text: [1.0, 0.0] if "apple" in text else [0.9, 0.1],
        raising=False,
    )
    sys.modules.setdefault("httpx", types.ModuleType("httpx"))
    neo4j_stub = sys.modules.setdefault("neo4j", types.ModuleType("neo4j"))
    neo4j_stub.GraphDatabase = object
    neo4j_stub.Driver = object
    jsonschema_stub = sys.modules.setdefault("jsonschema", types.ModuleType("jsonschema"))
    jsonschema_stub.validate = lambda *a, **k: None
    jsonschema_stub.ValidationError = type("VE", (Exception,), {})
    prom = sys.modules.setdefault("prometheus_client", types.ModuleType("prometheus_client"))
    prom.Counter = prom.Histogram = prom.Gauge = lambda *a, **k: None
    from ume.graph import MockGraph
    from ume.event import Event, EventType
    from ume.processing import apply_event_to_graph
    from ume.ontology import OntologyListener, configure_ontology_graph
    from ume._internal.listeners import register_listener, unregister_listener

    graph = MockGraph()
    configure_ontology_graph(graph)
    listener = OntologyListener()
    register_listener(listener)

    now = int(time.time())
    e1 = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=now,
        payload={"node_id": "n1", "attributes": {"text": "apple"}},
    )
    e2 = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=now,
        payload={"node_id": "n2", "attributes": {"text": "banana"}},
    )

    apply_event_to_graph(e1, graph)
    apply_event_to_graph(e2, graph)

    unregister_listener(listener)

    edges = graph.get_all_edges()
    assert ("n1", "n2", "RELATES_TO") in edges or ("n2", "n1", "RELATES_TO") in edges

