# tests/test_listeners.py
import time
import pytest

from ume import Event, EventType, MockGraph, apply_event_to_graph
from ume.listeners import register_listener, unregister_listener


class RecordingListener:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []

    def on_node_created(self, node_id: str, attributes: dict) -> None:
        self.calls.append(("node_created", (node_id, attributes)))

    def on_node_updated(self, node_id: str, attributes: dict) -> None:
        self.calls.append(("node_updated", (node_id, attributes)))

    def on_edge_created(self, source: str, target: str, label: str) -> None:
        self.calls.append(("edge_created", (source, target, label)))

    def on_edge_deleted(self, source: str, target: str, label: str) -> None:
        self.calls.append(("edge_deleted", (source, target, label)))


@pytest.fixture
def graph() -> MockGraph:
    return MockGraph()


def test_listener_receives_node_created_callback(graph: MockGraph) -> None:
    listener = RecordingListener()
    register_listener(listener)
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=int(time.time()),
        payload={"node_id": "n1", "attributes": {"a": 1, "type": "UserMemory"}},
    )
    apply_event_to_graph(event, graph)
    unregister_listener(listener)

    assert ("node_created", ("n1", {"a": 1, "type": "UserMemory"})) in listener.calls


def test_listener_receives_edge_created_callback(graph: MockGraph) -> None:
    graph.add_node("s", {})
    graph.add_node("t", {})
    listener = RecordingListener()
    register_listener(listener)
    event = Event(
        event_type=EventType.CREATE_EDGE,
        timestamp=int(time.time()),
        node_id="s",
        target_node_id="t",
        label="L",
        payload={},
    )
    apply_event_to_graph(event, graph)
    unregister_listener(listener)

    assert ("edge_created", ("s", "t", "L")) in listener.calls
