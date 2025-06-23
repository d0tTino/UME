import time
import pytest

from ume import Event, EventType, PolicyViolationError
from ume.plugins.alignment.rego_engine import RegoPolicyEngine

pytest.importorskip("regopy")


@pytest.fixture()
def engine():
    return RegoPolicyEngine("src/ume/plugins/alignment/policies")


def test_allow_event(engine):
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=int(time.time()),
        payload={"node_id": "ok", "attributes": {"type": "UserMemory"}},
    )
    engine.validate(event)


def test_forbidden_node(engine):
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=int(time.time()),
        payload={"node_id": "forbidden", "attributes": {"type": "UserMemory"}},
    )
    with pytest.raises(PolicyViolationError):
        engine.validate(event)


def test_admin_role_update(engine):
    event = Event(
        event_type=EventType.UPDATE_NODE_ATTRIBUTES,
        timestamp=int(time.time()),
        payload={"node_id": "user1", "attributes": {"role": "admin"}},
    )
    with pytest.raises(PolicyViolationError):
        engine.validate(event)


def test_admin_edge(engine):
    event = Event(
        event_type=EventType.CREATE_EDGE,
        timestamp=int(time.time()),
        payload={},
        node_id="admin",
        target_node_id="node2",
        label="related",
    )
    with pytest.raises(PolicyViolationError):
        engine.validate(event)
