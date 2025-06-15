import time
from ume import Event, EventType, MockGraph, apply_event_to_graph
from ume.vector_store import VectorStore, VectorStoreListener
from ume._internal.listeners import register_listener, unregister_listener


def test_vector_store_add_and_query() -> None:
    store = VectorStore(dim=2)
    store.add("a", [1.0, 0.0])
    store.add("b", [0.0, 1.0])
    res = store.query([1.0, 0.0], k=1)
    assert res == ["a"]


def test_vector_store_listener_on_create() -> None:
    store = VectorStore(dim=2)
    listener = VectorStoreListener(store)
    register_listener(listener)
    graph = MockGraph()
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=int(time.time()),
        payload={"node_id": "n1", "attributes": {"embedding": [1.0, 0.0]}},
    )
    apply_event_to_graph(event, graph)
    unregister_listener(listener)

    assert store.query([1.0, 0.0], k=1) == ["n1"]
