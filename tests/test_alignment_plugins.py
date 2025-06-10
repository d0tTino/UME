import time
import pytest
from ume import Event, EventType, apply_event_to_graph, MockGraph, PolicyViolationError


def test_forbidden_node_policy():
    graph = MockGraph()
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=int(time.time()),
        payload={"node_id": "forbidden", "attributes": {"type": "UserMemory"}},
    )
    with pytest.raises(PolicyViolationError):
        apply_event_to_graph(event, graph)
