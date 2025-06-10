import pytest

from ume import (
    GraphSchemaManager,
    GraphSchema,
    PersistentGraph,
    Event,
    EventType,
    apply_event_to_graph,
    ProcessingError,
)


@pytest.fixture
def graph() -> PersistentGraph:
    return PersistentGraph(":memory:")


def test_schema_manager_loads_versions():
    manager = GraphSchemaManager()
    versions = set(manager.available_versions())
    assert "1.0.0" in versions
    assert "2.0.0" in versions


def test_get_schema_returns_correct_version():
    manager = GraphSchemaManager()
    schema = manager.get_schema("2.0.0")
    assert isinstance(schema, GraphSchema)
    assert schema.version == "2.0.0"
    assert "NewType" in schema.node_types


def test_upgrade_schema_returns_new_version():
    manager = GraphSchemaManager()
    schema = manager.upgrade_schema("1.0.0", "2.0.0")
    assert schema.version == "2.0.0"


def test_apply_event_with_schema_version(graph: PersistentGraph):
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=1,
        payload={"node_id": "n1", "attributes": {"type": "NewType"}},
    )
    with pytest.raises(ProcessingError):
        apply_event_to_graph(event, graph)

    apply_event_to_graph(event, graph, schema_version="2.0.0")
    assert graph.node_exists("n1")
