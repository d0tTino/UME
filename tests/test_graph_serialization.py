# tests/test_graph_serialization.py
import json
import pytest
import pathlib  # Ensure pathlib is imported
from typing import Any
from ume import (
    MockGraph,
    snapshot_graph_to_file,
    load_graph_from_file,
    SnapshotError,
)  # Add new imports


def test_empty_graph_dump_and_serialization():
    """Test dumping an empty graph and serializing it."""
    graph = MockGraph()
    dumped_data = graph.dump()

    assert "nodes" in dumped_data
    assert dumped_data["nodes"] == {}
    assert "edges" in dumped_data  # New assertion
    assert dumped_data["edges"] == []  # New assertion

    # Test JSON serialization of the empty graph dump
    json_str = json.dumps(dumped_data)
    restored_data = json.loads(json_str)

    assert "nodes" in restored_data
    assert restored_data["nodes"] == {}
    assert "edges" in restored_data  # New assertion
    assert restored_data["edges"] == []  # New assertion


def test_graph_serialization_roundtrip_with_nodes_and_edges():
    """Test dumping a graph with nodes and edges, serializing, and deserializing."""
    graph = MockGraph()
    node_a_attrs = {"name": "Alice", "type": "person"}
    node_b_attrs = {"name": "Bob", "value": 42}

    graph.add_node("a", node_a_attrs)
    graph.add_node("b", node_b_attrs)
    graph.add_node("c", {})  # Node with empty attributes

    # Add some edges
    graph.add_edge("a", "b", "RELATES_TO")
    graph.add_edge("b", "c", "LINKS_TO")
    expected_edges = [("a", "b", "RELATES_TO"), ("b", "c", "LINKS_TO")]

    # Get the dump
    dumped_data = graph.dump()

    # Basic checks on the dumped data structure
    assert "nodes" in dumped_data
    assert len(dumped_data["nodes"]) == 3
    assert dumped_data["nodes"]["a"] == node_a_attrs
    assert dumped_data["nodes"]["b"] == node_b_attrs
    assert dumped_data["nodes"]["c"] == {}
    assert "edges" in dumped_data
    assert len(dumped_data["edges"]) == 2
    assert set(map(tuple, dumped_data["edges"])) == set(
        map(tuple, expected_edges)
    )  # Compare content, order-agnostic

    # Perform JSON serialization and deserialization (roundtrip)
    json_str = json.dumps(dumped_data)
    restored_data_from_json = json.loads(json_str)

    # Verify the restored data
    assert "nodes" in restored_data_from_json
    assert len(restored_data_from_json["nodes"]) == 3
    assert restored_data_from_json["nodes"]["a"] == node_a_attrs
    assert restored_data_from_json["nodes"]["b"] == node_b_attrs
    assert restored_data_from_json["nodes"]["c"] == {}
    assert "edges" in restored_data_from_json
    assert len(restored_data_from_json["edges"]) == 2
    assert set(map(tuple, restored_data_from_json["edges"])) == set(
        map(tuple, expected_edges)
    )

    # Ensure original graph is not affected by modifications to dumped_data (due to .copy())
    dumped_data["nodes"]["a"]["name"] = "Changed Name"
    assert graph.get_node("a")["name"] == "Alice"
    if dumped_data["edges"]:  # If there are edges
        dumped_data["edges"][0] = (
            "c",
            "a",
            "MODIFIED_REL",
        )  # Try to modify dumped edge
        original_edges_in_graph = graph.get_all_edges()  # Get fresh copy
        assert set(map(tuple, original_edges_in_graph)) == set(
            map(tuple, expected_edges)
        )


def test_dump_returns_copy_not_reference():
    """Test that graph.dump()['nodes'] is a copy, not a reference to internal _nodes."""
    graph = MockGraph()
    node_attrs = {"feature": "original"}
    graph.add_node("node1", node_attrs)

    dumped_nodes = graph.dump()["nodes"]

    # Modify the dumped_nodes dictionary
    dumped_nodes["node1"]["feature"] = "modified_in_dump"
    dumped_nodes["new_node_in_dump"] = {"data": "test"}

    # Check that the original graph's _nodes dictionary is unchanged
    original_node_attrs = graph.get_node("node1")
    assert original_node_attrs is not None
    assert original_node_attrs["feature"] == "original"
    assert graph.node_exists("new_node_in_dump") is False
    assert len(graph._nodes) == 1  # Accessing protected member for test validation


# New tests for snapshot_graph_to_file


def test_snapshot_empty_graph_roundtrip(tmp_path: pathlib.Path):
    """Test snapshotting an empty graph and restoring it from file."""
    graph = MockGraph()
    snapshot_file_path = tmp_path / "empty_snapshot.json"

    # Create snapshot
    snapshot_graph_to_file(graph, snapshot_file_path)

    # Check if file was created
    assert snapshot_file_path.is_file()

    # Read back and verify
    with open(snapshot_file_path, "r", encoding="utf-8") as f:
        restored_data = json.load(f)

    assert "nodes" in restored_data
    assert restored_data["nodes"] == {}  # Empty graph should have empty nodes dict


def test_snapshot_graph_with_nodes_roundtrip(tmp_path: pathlib.Path):
    """Test snapshotting a graph with nodes and restoring it from file."""
    graph = MockGraph()
    node_a_attrs = {"name": "Alice", "age": 30, "tags": ["dev", "python"]}
    node_b_attrs = {"name": "Bob", "department": "HR", "active": True}
    node_c_attrs: dict[str, Any] = {}  # Node with empty attributes

    graph.add_node("nodeA", node_a_attrs)
    graph.add_node("nodeB", node_b_attrs)
    graph.add_node("nodeC", node_c_attrs)

    snapshot_file_path = tmp_path / "populated_snapshot.json"

    # Create snapshot
    snapshot_graph_to_file(graph, snapshot_file_path)

    # Check if file was created
    assert snapshot_file_path.is_file()

    # Read back and verify
    with open(snapshot_file_path, "r", encoding="utf-8") as f:
        restored_data = json.load(f)

    assert "nodes" in restored_data
    assert len(restored_data["nodes"]) == 3

    # Verify content of each node
    assert restored_data["nodes"].get("nodeA") == node_a_attrs
    assert restored_data["nodes"].get("nodeB") == node_b_attrs
    assert restored_data["nodes"].get("nodeC") == node_c_attrs

    # Verify a non-existent node is not in restored data
    assert "nodeD" not in restored_data["nodes"]


def test_snapshot_file_content_is_pretty_printed(tmp_path: pathlib.Path):
    """Verify that the snapshot JSON file is pretty-printed."""
    graph = MockGraph()
    graph.add_node("node1", {"name": "Test", "data": [1, 2]})
    snapshot_file_path = tmp_path / "pretty_print_test.json"

    snapshot_graph_to_file(graph, snapshot_file_path)

    with open(snapshot_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for newlines and spaces indicative of pretty-printing (indent=2)
    assert "\n" in content
    assert '  "nodes"' in content


# --- Tests for load_graph_from_file ---


def test_load_graph_from_file_success_empty_graph(tmp_path: pathlib.Path):
    """Test loading an empty graph from a valid snapshot file."""
    graph = MockGraph()
    snapshot_file = tmp_path / "empty_graph_to_load.json"
    snapshot_graph_to_file(graph, snapshot_file)

    loaded_graph = load_graph_from_file(snapshot_file)
    assert isinstance(loaded_graph, MockGraph)
    assert loaded_graph.node_count == 0
    assert loaded_graph.dump()["nodes"] == {}
    assert loaded_graph.get_all_edges() == []  # New assertion


def test_load_graph_from_file_success_populated_graph(tmp_path: pathlib.Path):
    """Test loading a populated graph from a valid snapshot file."""
    original_graph = MockGraph()
    attrs1 = {"name": "Node 1", "value": 10}
    attrs2 = {"name": "Node 2", "active": True}
    original_graph.add_node("n1", attrs1)
    original_graph.add_node("n2", attrs2)
    original_graph.add_edge("n1", "n2", "CONNECTS_TO")
    expected_edges = [("n1", "n2", "CONNECTS_TO")]

    snapshot_file = tmp_path / "populated_graph_to_load.json"
    snapshot_graph_to_file(original_graph, snapshot_file)

    loaded_graph = load_graph_from_file(snapshot_file)
    assert isinstance(loaded_graph, MockGraph)
    assert loaded_graph.node_count == 2
    assert loaded_graph.get_node("n1") == attrs1
    assert loaded_graph.get_node("n2") == attrs2
    assert set(map(tuple, loaded_graph.get_all_edges())) == set(
        map(tuple, expected_edges)
    )
    assert original_graph.dump() == loaded_graph.dump()  # Compare full dumps


def test_load_graph_from_file_file_not_found(tmp_path: pathlib.Path):
    """Test load_graph_from_file with a non-existent file path."""
    non_existent_file = tmp_path / "this_file_does_not_exist.json"
    with pytest.raises(
        FileNotFoundError, match=f"Snapshot file not found at path: {non_existent_file}"
    ):
        load_graph_from_file(non_existent_file)


def test_load_graph_from_file_malformed_json(tmp_path: pathlib.Path):
    """Test load_graph_from_file with a file containing malformed JSON."""
    snapshot_file = tmp_path / "malformed.json"
    with open(snapshot_file, "w", encoding="utf-8") as f:
        f.write(
            "{'nodes': 'this is not valid json because of single quotes'..."
        )  # Malformed JSON

    with pytest.raises(json.JSONDecodeError):  # Check for the specific error type
        load_graph_from_file(snapshot_file)


def test_load_graph_from_file_invalid_structure_no_nodes_key(tmp_path: pathlib.Path):
    """Test load_graph_from_file with JSON missing the root 'nodes' key."""
    snapshot_file = tmp_path / "invalid_structure_no_nodes.json"
    with open(snapshot_file, "w", encoding="utf-8") as f:
        json.dump({"other_key": {}}, f)  # Missing 'nodes'

    with pytest.raises(
        SnapshotError,
        match="Invalid snapshot format: missing 'nodes' key at the root level.",
    ):
        load_graph_from_file(snapshot_file)


def test_load_graph_from_file_invalid_structure_nodes_not_dict(tmp_path: pathlib.Path):
    """Test load_graph_from_file where 'nodes' is not a dictionary."""
    snapshot_file = tmp_path / "invalid_structure_nodes_not_dict.json"
    with open(snapshot_file, "w", encoding="utf-8") as f:
        json.dump({"nodes": ["not", "a", "dict"]}, f)  # 'nodes' is a list

    with pytest.raises(
        SnapshotError, match="Invalid snapshot format: 'nodes' should be a dictionary"
    ):
        load_graph_from_file(snapshot_file)


def test_load_graph_from_file_invalid_structure_attributes_not_dict(
    tmp_path: pathlib.Path,
):
    """Test load_graph_from_file where a node's attributes are not a dictionary."""
    snapshot_file = tmp_path / "invalid_structure_attrs_not_dict.json"
    with open(snapshot_file, "w", encoding="utf-8") as f:
        json.dump({"nodes": {"node1": "not_an_attributes_dict"}}, f)

    with pytest.raises(
        SnapshotError,
        match="Invalid snapshot format for node 'node1': attributes should be a dictionary",
    ):
        load_graph_from_file(snapshot_file)


def test_load_graph_from_file_root_not_dict(tmp_path: pathlib.Path):
    """Test load_graph_from_file where the JSON root is not a dictionary."""
    snapshot_file = tmp_path / "invalid_root_not_dict.json"
    with open(snapshot_file, "w", encoding="utf-8") as f:
        json.dump(["just", "a", "list"], f)  # Root is a list

    with pytest.raises(
        SnapshotError, match="Invalid snapshot format: root should be a dictionary"
    ):
        load_graph_from_file(snapshot_file)


def test_load_graph_from_file_snapshot_with_empty_edges_list(tmp_path: pathlib.Path):
    """Test loading a snapshot that explicitly contains an empty 'edges' list."""
    snapshot_file = tmp_path / "snapshot_empty_edges.json"
    snapshot_data = {"nodes": {"n1": {"attr": "val"}}, "edges": []}
    with open(snapshot_file, "w", encoding="utf-8") as f:
        json.dump(snapshot_data, f)

    loaded_graph = load_graph_from_file(snapshot_file)
    assert loaded_graph.node_exists("n1")
    assert loaded_graph.get_all_edges() == []


def test_load_graph_from_file_invalid_structure_edges_not_list(tmp_path: pathlib.Path):
    """Test load_graph_from_file where 'edges' is not a list."""
    snapshot_file = tmp_path / "invalid_edges_not_list.json"
    with open(snapshot_file, "w", encoding="utf-8") as f:
        json.dump({"nodes": {}, "edges": {"not": "a list"}}, f)

    with pytest.raises(
        SnapshotError, match="Invalid snapshot format: 'edges' should be a list"
    ):
        load_graph_from_file(snapshot_file)


def test_load_graph_from_file_invalid_structure_edge_item_not_list_or_tuple(
    tmp_path: pathlib.Path,
):
    """Test load_graph_from_file where an edge item is not a list/tuple."""
    snapshot_file = tmp_path / "invalid_edge_item_type.json"
    with open(snapshot_file, "w", encoding="utf-8") as f:
        json.dump({"nodes": {}, "edges": ["not-a-list-or-tuple"]}, f)

    with pytest.raises(
        SnapshotError,
        match="Invalid snapshot format for edge at index 0: each edge should be a list or tuple",
    ):
        load_graph_from_file(snapshot_file)


def test_load_graph_from_file_invalid_structure_edge_item_wrong_length(
    tmp_path: pathlib.Path,
):
    """Test load_graph_from_file where an edge item does not have 3 elements."""
    snapshot_file = tmp_path / "invalid_edge_item_length.json"
    with open(snapshot_file, "w", encoding="utf-8") as f:
        json.dump({"nodes": {}, "edges": [("n1", "n2")]}, f)  # Only 2 elements

    with pytest.raises(
        SnapshotError,
        match="Invalid snapshot format for edge at index 0: each edge must have 3 elements",
    ):
        load_graph_from_file(snapshot_file)


def test_load_graph_from_file_invalid_structure_edge_element_not_string(
    tmp_path: pathlib.Path,
):
    """Test load_graph_from_file where an edge element (source, target, or label) is not a string."""
    snapshot_file = tmp_path / "invalid_edge_element_type.json"
    with open(snapshot_file, "w", encoding="utf-8") as f:
        json.dump({"nodes": {}, "edges": [("n1", "n2", 123)]}, f)  # Label is int

    with pytest.raises(
        SnapshotError,
        match="Invalid snapshot format for edge at index 0: all edge elements .* must be strings",
    ):
        load_graph_from_file(snapshot_file)
