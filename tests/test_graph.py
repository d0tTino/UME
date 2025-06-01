# tests/test_graph.py
import pytest
from ume import MockGraph, ProcessingError # IGraphAdapter is implicitly tested by testing MockGraph's adherence
from ume.graph_adapter import IGraphAdapter # Import for isinstance check if needed

# Fixture for a clean MockGraph instance
@pytest.fixture
def graph() -> MockGraph:
    """Provides a clean MockGraph instance for each test."""
    return MockGraph()

def test_mockgraph_is_igraph_adapter_instance(graph: MockGraph):
    """Test that MockGraph is an instance of IGraphAdapter."""
    assert isinstance(graph, IGraphAdapter)

# --- add_node tests ---
def test_add_node_success(graph: MockGraph):
    """Test adding a new node successfully."""
    node_id = "node1"
    attributes = {"name": "Test Node", "value": 123}
    graph.add_node(node_id, attributes)
    assert graph.node_exists(node_id)
    assert graph.get_node(node_id) == attributes
    assert graph.node_count == 1

def test_add_node_empty_attributes_success(graph: MockGraph):
    """Test adding a new node with empty attributes successfully."""
    node_id = "node_empty_attr"
    attributes = {}
    graph.add_node(node_id, attributes)
    assert graph.node_exists(node_id)
    assert graph.get_node(node_id) == {}

def test_add_node_duplicate_raises_error(graph: MockGraph):
    """Test that adding a node with an existing ID raises ProcessingError."""
    node_id = "node1"
    attributes1 = {"name": "First Node"}
    attributes2 = {"name": "Second Node"}
    graph.add_node(node_id, attributes1) # First add
    with pytest.raises(ProcessingError, match=f"Node '{node_id}' already exists."):
        graph.add_node(node_id, attributes2) # Attempt duplicate add

# --- update_node tests ---
def test_update_node_success(graph: MockGraph):
    """Test updating an existing node's attributes successfully."""
    node_id = "node1"
    initial_attributes = {"name": "Initial Name", "version": 1}
    update_attributes = {"version": 2, "status": "updated"}
    expected_attributes = {"name": "Initial Name", "version": 2, "status": "updated"}

    graph.add_node(node_id, initial_attributes)
    graph.update_node(node_id, update_attributes)

    assert graph.get_node(node_id) == expected_attributes

def test_update_node_with_empty_attributes_dict(graph: MockGraph):
    """Test updating with an empty attributes dictionary (should result in no change)."""
    node_id = "node1"
    initial_attributes = {"name": "Initial Name"}
    graph.add_node(node_id, initial_attributes.copy()) # Add with copy

    graph.update_node(node_id, {}) # Update with empty dict

    assert graph.get_node(node_id) == initial_attributes # Attributes should remain unchanged

def test_update_node_non_existent_raises_error(graph: MockGraph):
    """Test that updating a non-existent node raises ProcessingError."""
    node_id = "node_not_found"
    attributes = {"name": "Attempted Update"}
    with pytest.raises(ProcessingError, match=f"Node '{node_id}' not found for update."):
        graph.update_node(node_id, attributes)

# --- get_node tests ---
def test_get_node_exists(graph: MockGraph):
    """Test get_node for an existing node."""
    node_id = "node1"
    attributes = {"data": "some_data"}
    graph.add_node(node_id, attributes)
    assert graph.get_node(node_id) == attributes

def test_get_node_not_exists(graph: MockGraph):
    """Test get_node for a non-existent node."""
    assert graph.get_node("node_not_found") is None

# --- node_exists tests ---
def test_node_exists_true(graph: MockGraph):
    """Test node_exists for an existing node."""
    node_id = "node1"
    graph.add_node(node_id, {})
    assert graph.node_exists(node_id) is True

def test_node_exists_false(graph: MockGraph):
    """Test node_exists for a non-existent node."""
    assert graph.node_exists("node_not_found") is False

# --- clear tests ---
def test_clear_graph_with_nodes_and_edges(graph: MockGraph): # Renamed for clarity
    """Test clearing the graph with both nodes and edges."""
    graph.add_node("n1", {})
    graph.add_node("n2", {})
    graph.add_edge("n1", "n2", "LINKS_TO")

    assert graph.node_count == 2
    assert len(graph.get_all_edges()) == 1

    graph.clear()

    assert graph.node_count == 0
    assert graph.get_all_edges() == []
    assert graph.node_exists("n1") is False
    assert graph.dump() == {"nodes": {}, "edges": []} # Check dump output

# --- dump tests (basic check, detailed serialization in test_graph_serialization.py) ---
def test_dump_structure(graph: MockGraph):
    """Test the basic structure of the dump method output."""
    node_id = "node1"
    attributes = {"key": "value"}
    graph.add_node(node_id, attributes)
    dump_data = graph.dump()
    assert "nodes" in dump_data
    assert node_id in dump_data["nodes"]
    assert dump_data["nodes"][node_id] == attributes

def test_dump_empty_graph_structure(graph: MockGraph):
    """Test dump structure for an empty graph."""
    dump_data = graph.dump()
    assert "nodes" in dump_data
    assert dump_data["nodes"] == {}

# --- get_all_node_ids tests ---
def test_get_all_node_ids_empty_graph(graph: MockGraph):
    """Test get_all_node_ids on an empty graph."""
    assert graph.get_all_node_ids() == []

def test_get_all_node_ids_populated_graph(graph: MockGraph):
    """Test get_all_node_ids on a graph with multiple nodes."""
    graph.add_node("node1", {})
    graph.add_node("node2", {"data": "value"})
    graph.add_node("alpha", {"name": "Alpha Node"})

    node_ids = graph.get_all_node_ids()
    assert isinstance(node_ids, list)
    assert len(node_ids) == 3
    # Order is not guaranteed by dict.keys(), so check with sets
    assert set(node_ids) == {"node1", "node2", "alpha"}

# --- add_edge tests (New) ---
def test_add_edge_success(graph: MockGraph):
    """Test adding a valid edge successfully."""
    graph.add_node("nodeS", {})
    graph.add_node("nodeT", {})
    graph.add_edge("nodeS", "nodeT", "RELATES_TO")
    assert ("nodeS", "nodeT", "RELATES_TO") in graph._edges # Accessing protected member for test validation
    # Check get_all_edges as well
    all_edges = graph.get_all_edges()
    assert len(all_edges) == 1
    assert ("nodeS", "nodeT", "RELATES_TO") in all_edges

def test_add_edge_missing_source_node_raises_error(graph: MockGraph):
    """Test ProcessingError when adding an edge with a non-existent source node."""
    graph.add_node("nodeT", {}) # Target node exists
    with pytest.raises(ProcessingError, match="Both source node 'nodeS_missing' and target node 'nodeT' must exist"):
        graph.add_edge("nodeS_missing", "nodeT", "LINKS_TO")

def test_add_edge_missing_target_node_raises_error(graph: MockGraph):
    """Test ProcessingError when adding an edge with a non-existent target node."""
    graph.add_node("nodeS", {}) # Source node exists
    with pytest.raises(ProcessingError, match="Both source node 'nodeS' and target node 'nodeT_missing' must exist"):
        graph.add_edge("nodeS", "nodeT_missing", "CONNECTS_TO")

def test_add_edge_both_nodes_missing_raises_error(graph: MockGraph):
    """Test ProcessingError when adding an edge with both source and target nodes non-existent."""
    with pytest.raises(ProcessingError, match="Both source node 'nodeS_missing' and target node 'nodeT_missing' must exist"):
        graph.add_edge("nodeS_missing", "nodeT_missing", "IS_RELATED_TO")

# --- get_all_edges tests (New) ---
def test_get_all_edges_empty_graph(graph: MockGraph):
    """Test get_all_edges on a graph with no edges (and no nodes)."""
    assert graph.get_all_edges() == []

def test_get_all_edges_no_edges_but_nodes_exist(graph: MockGraph):
    """Test get_all_edges on a graph with nodes but no edges."""
    graph.add_node("node1", {})
    graph.add_node("node2", {})
    assert graph.get_all_edges() == []

def test_get_all_edges_populated(graph: MockGraph):
    """Test get_all_edges on a graph with multiple edges."""
    graph.add_node("n1", {})
    graph.add_node("n2", {})
    graph.add_node("n3", {})
    graph.add_edge("n1", "n2", "L1")
    graph.add_edge("n2", "n3", "L2")
    graph.add_edge("n1", "n3", "L3")

    edges = graph.get_all_edges()
    assert isinstance(edges, list)
    assert len(edges) == 3
    # Use set of tuples for order-agnostic comparison
    expected_edges = {("n1", "n2", "L1"), ("n2", "n3", "L2"), ("n1", "n3", "L3")}
    assert set(edges) == expected_edges

    # Test that it returns a copy
    edges.append(("n3", "n1", "L4_local_copy"))
    assert len(graph.get_all_edges()) == 3

# --- find_connected_nodes tests ---
# Old test_find_connected_nodes_existing_node_returns_empty_list removed as behavior changed.

def test_find_connected_nodes_non_existent_node_raises_error(graph: MockGraph):
    """
    Test find_connected_nodes for a non-existent node.
    Should raise ProcessingError.
    """
    with pytest.raises(ProcessingError, match="Node 'node_not_found' not found."):
        graph.find_connected_nodes("node_not_found")

    with pytest.raises(ProcessingError, match="Node 'another_missing' not found."):
        graph.find_connected_nodes("another_missing", edge_label="ANY_LABEL")

def test_find_connected_nodes_with_edges(graph: MockGraph):
    """Test find_connected_nodes when edges exist."""
    graph.add_node("n1", {})
    graph.add_node("n2", {})
    graph.add_node("n3", {})
    graph.add_node("n4", {})
    graph.add_edge("n1", "n2", "RELATES_TO")
    graph.add_edge("n1", "n3", "RELATES_TO")
    graph.add_edge("n1", "n4", "DIFFERENT_REL")
    graph.add_edge("n2", "n3", "RELATES_TO") # Edge from different source

    # Test without label filter
    connected = graph.find_connected_nodes("n1")
    assert isinstance(connected, list)
    assert set(connected) == {"n2", "n3", "n4"}

    # Test with label filter
    connected_relates_to = graph.find_connected_nodes("n1", edge_label="RELATES_TO")
    assert set(connected_relates_to) == {"n2", "n3"}

    connected_different_rel = graph.find_connected_nodes("n1", edge_label="DIFFERENT_REL")
    assert set(connected_different_rel) == {"n4"}

def test_find_connected_nodes_no_matching_edges(graph: MockGraph):
    """Test find_connected_nodes when no outgoing edges match."""
    graph.add_node("n1", {})
    graph.add_node("n2", {})
    graph.add_edge("n1", "n2", "RELATES_TO") # Edge exists

    # Test with a non-matching label
    assert graph.find_connected_nodes("n1", edge_label="NON_EXISTENT_LABEL") == []
    # Test for a node with no outgoing edges
    graph.add_node("n3", {})
    assert graph.find_connected_nodes("n3") == []

```
