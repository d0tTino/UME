import subprocess
from pathlib import Path
import sys
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


def test_proto_lookup():
    manager = GraphSchemaManager()
    proto = manager.get_proto("1.0.0")
    assert hasattr(proto, "Graph")


def test_register_schema(tmp_path: Path):
    manager = GraphSchemaManager()
    schema_file = tmp_path / "s.yaml"
    schema_file.write_text("version: '3.0.0'")
    proto_file = tmp_path / "dummy.proto"
    proto_file.write_text(
        "syntax = 'proto3'; package x; message Graph {}"
    )
    out_dir = tmp_path
    subprocess.run(
        ["protoc", f"-I={tmp_path}", f"--python_out={out_dir}", str(proto_file)],
        check=True,
    )
    sys.path.insert(0, str(tmp_path))
    manager.register_schema(
        "3.0.0", str(schema_file), f"{proto_file.stem}_pb2"
    )
    assert "3.0.0" in manager.available_versions()


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


def test_upgrade_transforms_graph(graph: PersistentGraph) -> None:
    graph.add_node("a", {})
    graph.add_node("b", {})
    graph.add_edge("a", "b", "L")
    graph.add_edge("b", "a", "TO_DELETE")

    manager = GraphSchemaManager()
    manager.upgrade_schema("1.0.0", "2.0.0", graph)

    edges = graph.get_all_edges()
    assert ("a", "b", "LINKS_TO") in edges
    assert all(lbl != "L" for _, _, lbl in edges)
    assert all(lbl != "TO_DELETE" for _, _, lbl in edges)
