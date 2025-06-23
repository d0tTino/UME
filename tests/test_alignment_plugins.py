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


def test_rego_policy_engine():
    pytest.importorskip("regopy")
    from ume.plugins.alignment.rego_engine import RegoPolicyEngine
    engine = RegoPolicyEngine("src/ume/plugins/alignment/policies")
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=int(time.time()),
        payload={"node_id": "forbidden", "attributes": {"type": "UserMemory"}},
    )
    with pytest.raises(PolicyViolationError):
        engine.validate(event)
