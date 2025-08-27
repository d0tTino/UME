import subprocess
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ume.schema_manager import GraphSchemaManager
from ume.graph_schema import GraphSchema
from ume.persistent_graph import PersistentGraph
from ume.event import Event, EventType
from ume.processing import apply_event_to_graph, ProcessingError


@pytest.fixture
def graph() -> PersistentGraph:
    return PersistentGraph(":memory:")


def test_schema_manager_loads_versions():
    manager = GraphSchemaManager()
    versions = set(manager.available_versions())
    assert "1.0.0" in versions
    assert "2.0.0" in versions
    assert "3.0.0" in versions


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
    proto3 = manager.get_proto("3.0.0")
    assert hasattr(proto3, "Graph")


def test_get_edge_version_manager():
    manager = GraphSchemaManager()
    assert manager.get_edge_version("OWNED_BY") == "3.0.0"


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
    assert ("a", "b", "LINKS_TO", {"version": "2.0.0"}) in edges
    assert all(lbl != "L" for _, _, lbl, _ in edges)
    assert all(lbl != "TO_DELETE" for _, _, lbl, _ in edges)


def test_upgrade_to_v3_transforms_graph(graph: PersistentGraph) -> None:
    graph.add_node("a", {})
    graph.add_node("b", {})
    graph.add_edge("a", "b", "L")
    graph.add_edge("b", "a", "TO_DELETE")
    graph.add_edge("a", "b", "NEW_LABEL")
    graph.add_edge("b", "a", "REMEMBERS")

    manager = GraphSchemaManager()
    manager.upgrade_schema("1.0.0", "3.0.0", graph)

    edges = graph.get_all_edges()
    assert (
        "a",
        "b",
        "TAGGED_AS",
        {"permission_level": "public", "version": "3.0.0"},
    ) in edges
    assert all(lbl == "TAGGED_AS" for _, _, lbl, _ in edges)


def test_upgrade_sets_edge_version(graph: PersistentGraph) -> None:
    graph.add_node("a", {})
    graph.add_node("b", {})
    graph.add_edge("a", "b", "NEW_LABEL")

    manager = GraphSchemaManager()
    manager.upgrade_schema("2.0.0", "3.0.0", graph)

    edges = graph.get_all_edges()
    assert (
        "a",
        "b",
        "TAGGED_AS",
        {"permission_level": "public", "version": "3.0.0"},
    ) in edges


def test_upgrade_maps_has_permission_edges(
    graph: PersistentGraph,
) -> None:
    graph.add_node("doc", {})
    graph.add_node("user1", {})
    graph.add_node("user2", {})
    graph.add_edge(
        "doc", "user1", "HAS_PERMISSION", {"permission_level": "editor"}
    )
    graph.add_edge(
        "doc", "user2", "HAS_PERMISSION", {"permission_level": "viewer"}
    )

    manager = GraphSchemaManager()
    manager.upgrade_schema("2.0.0", "3.0.0", graph)

    edges = graph.get_all_edges()
    assert (
        "doc",
        "user1",
        "OWNED_BY",
        {"permission_level": "public", "version": "3.0.0"},
    ) in edges
    assert (
        "doc",
        "user2",
        "SHARED_WITH",
        {"permission_level": "public", "version": "3.0.0"},
    ) in edges
    assert all(lbl != "HAS_PERMISSION" for _, _, lbl, _ in edges)


def test_upgrade_permission_nodes_multi_user(graph: PersistentGraph) -> None:
    graph.add_node("doc", {})
    graph.add_node("u1", {})
    graph.add_node("u2", {"name": "Bob"})
    graph.add_edge("doc", "u1", "HAS_PERMISSION", {"permission_level": "viewer"})
    graph.add_edge("doc", "u2", "HAS_PERMISSION", {"permission_level": "editor"})

    manager = GraphSchemaManager()
    manager.upgrade_schema("2.0.0", "3.0.0", graph)

    edges = graph.get_all_edges()
    assert (
        "doc",
        "u1",
        "SHARED_WITH",
        {"permission_level": "public", "version": "3.0.0"},
    ) in edges
    assert (
        "doc",
        "u2",
        "OWNED_BY",
        {"permission_level": "public", "version": "3.0.0"},
    ) in edges

    assert graph.get_node("u1") == {
        "type": "User",
        "permission_level": "public",
    }
    assert graph.get_node("u2") == {
        "name": "Bob",
        "type": "User",
        "permission_level": "public",
    }


def test_upgrade_preserves_schema_version(graph: PersistentGraph) -> None:
    graph.add_node("a", {"schema_version": "2.0.0"})
    graph.add_node("b", {"schema_version": "2.0.0"})
    graph.add_edge(
        "a", "b", "NEW_LABEL", {"schema_version": "2.0.0"}
    )

    manager = GraphSchemaManager()
    manager.upgrade_schema("2.0.0", "3.0.0", graph)

    assert graph.get_node("a")["schema_version"] == "2.0.0"
    edges = graph.get_all_edges()
    assert (
        "a",
        "b",
        "TAGGED_AS",
        {
            "permission_level": "public",
            "schema_version": "2.0.0",
            "version": "3.0.0",
        },
    ) in edges


def test_upgrade_adds_version_when_missing(graph: PersistentGraph) -> None:
    graph.add_node("a", {})
    graph.add_node("b", {})
    graph.add_edge("a", "b", "TAGGED_AS")

    manager = GraphSchemaManager()
    manager.upgrade_schema("2.0.0", "3.0.0", graph)

    edges = graph.get_all_edges()
    assert (
        "a",
        "b",
        "TAGGED_AS",
        {"permission_level": "public", "version": "3.0.0"},
    ) in edges
