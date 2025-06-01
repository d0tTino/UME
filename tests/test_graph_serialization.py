# tests/test_graph_serialization.py
import json
import pytest
from ume import MockGraph # Assuming MockGraph is exported via ume.__init__

def test_empty_graph_dump_and_serialization():
    """Test dumping an empty graph and serializing it."""
    graph = MockGraph()
    dumped_data = graph.dump()

    assert "nodes" in dumped_data
    assert dumped_data["nodes"] == {}

    # Test JSON serialization of the empty graph dump
    json_str = json.dumps(dumped_data)
    restored_data = json.loads(json_str)

    assert "nodes" in restored_data
    assert restored_data["nodes"] == {}

def test_graph_serialization_roundtrip_with_nodes():
    """Test dumping a graph with nodes, serializing, and deserializing."""
    graph = MockGraph()
    node_a_attrs = {"name": "Alice", "type": "person"}
    node_b_attrs = {"name": "Bob", "value": 42}

    graph.add_node("a", node_a_attrs)
    graph.add_node("b", node_b_attrs)
    graph.add_node("c", {}) # Node with empty attributes

    # Get the dump
    dumped_data = graph.dump()

    # Basic checks on the dumped data structure
    assert "nodes" in dumped_data
    assert len(dumped_data["nodes"]) == 3
    assert dumped_data["nodes"]["a"] == node_a_attrs
    assert dumped_data["nodes"]["b"] == node_b_attrs
    assert dumped_data["nodes"]["c"] == {}

    # Perform JSON serialization and deserialization (roundtrip)
    json_str = json.dumps(dumped_data)
    restored_data_from_json = json.loads(json_str)

    # Verify the restored data
    assert "nodes" in restored_data_from_json
    assert len(restored_data_from_json["nodes"]) == 3
    assert restored_data_from_json["nodes"]["a"] == node_a_attrs
    assert restored_data_from_json["nodes"]["b"] == node_b_attrs
    assert restored_data_from_json["nodes"]["c"] == {}

    # Ensure original graph is not affected by modifications to dumped_data (due to .copy())
    dumped_data["nodes"]["a"]["name"] = "Changed Name"
    assert graph.get_node("a")["name"] == "Alice"


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
    assert len(graph._nodes) == 1 # Accessing protected member for test validation

```
