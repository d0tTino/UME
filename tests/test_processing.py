# tests/test_processing.py
import pytest
import time
import re
from ume import Event, MockGraph, apply_event_to_graph, ProcessingError

@pytest.fixture
def graph() -> MockGraph:
    """Pytest fixture to provide a clean MockGraph instance for each test."""
    return MockGraph()

def test_apply_create_node_event_success(graph: MockGraph):
    """Test successfully creating a new node."""
    event_id = "event1"
    node_id = "node1"
    attributes = {"name": "Test Node", "value": 100}
    event = Event(
        event_id=event_id,
        event_type="CREATE_NODE",
        timestamp=int(time.time()),
        payload={"node_id": node_id, "attributes": attributes}
    )
    apply_event_to_graph(event, graph)
    assert graph.node_exists(node_id)
    assert graph.get_node(node_id) == attributes
    assert graph.node_count == 1

def test_apply_create_node_event_no_attributes(graph: MockGraph):
    """Test successfully creating a new node with no initial attributes."""
    node_id = "node_no_attr"
    event = Event(
        event_type="CREATE_NODE",
        timestamp=int(time.time()),
        payload={"node_id": node_id} # Attributes are optional in payload for create
    )
    apply_event_to_graph(event, graph)
    assert graph.node_exists(node_id)
    assert graph.get_node(node_id) == {} # Should be an empty dict

def test_apply_create_node_event_already_exists(graph: MockGraph):
    """Test error when trying to create a node that already exists."""
    node_id = "node1"
    graph.add_node(node_id, {"name": "Initial Node"}) # Pre-existing node
    event = Event(
        event_type="CREATE_NODE",
        timestamp=int(time.time()),
        payload={"node_id": node_id, "attributes": {"name": "New Node"}}
    )
    with pytest.raises(ProcessingError, match=f"Node '{node_id}' already exists"):
        apply_event_to_graph(event, graph)

def test_apply_create_node_missing_node_id(graph: MockGraph):
    """Test error when 'node_id' is missing in payload for CREATE_NODE."""
    event = Event(
        event_type="CREATE_NODE",
        timestamp=int(time.time()),
        payload={"attributes": {"name": "Test Node"}}
    )
    with pytest.raises(ProcessingError, match="Missing 'node_id' in payload for CREATE_NODE event"):
        apply_event_to_graph(event, graph)

def test_apply_create_node_invalid_node_id_type(graph: MockGraph):
    """Test error when 'node_id' is not a string for CREATE_NODE."""
    event = Event(
        event_type="CREATE_NODE",
        timestamp=int(time.time()),
        payload={"node_id": 123, "attributes": {"name": "Test Node"}},  # type: ignore[arg-type]
    )
    with pytest.raises(ProcessingError, match="'node_id' must be a string for CREATE_NODE event"):
        apply_event_to_graph(event, graph)

def test_apply_update_node_attributes_success(graph: MockGraph):
    """Test successfully updating attributes of an existing node."""
    node_id = "node1"
    initial_attrs = {"name": "Initial Name", "status": "active"}
    updated_attrs = {"status": "inactive", "version": 2}
    expected_final_attrs = {"name": "Initial Name", "status": "inactive", "version": 2}

    graph.add_node(node_id, initial_attrs)
    event = Event(
        event_type="UPDATE_NODE_ATTRIBUTES",
        timestamp=int(time.time()),
        payload={"node_id": node_id, "attributes": updated_attrs}
    )
    apply_event_to_graph(event, graph)
    assert graph.get_node(node_id) == expected_final_attrs

def test_apply_update_node_attributes_node_not_exists(graph: MockGraph):
    """Test error when trying to update attributes of a non-existent node."""
    node_id = "node_not_found"
    event = Event(
        event_type="UPDATE_NODE_ATTRIBUTES",
        timestamp=int(time.time()),
        payload={"node_id": node_id, "attributes": {"name": "Updated Name"}}
    )
    with pytest.raises(ProcessingError, match=re.escape(f"Node '{node_id}' not found for update.")):
        apply_event_to_graph(event, graph)

def test_apply_update_node_attributes_missing_node_id(graph: MockGraph):
    """Test error for UPDATE_NODE_ATTRIBUTES if 'node_id' is missing."""
    event = Event(
        event_type="UPDATE_NODE_ATTRIBUTES",
        timestamp=int(time.time()),
        payload={"attributes": {"name": "Updated Name"}}
    )
    with pytest.raises(ProcessingError, match="Missing 'node_id' in payload for UPDATE_NODE_ATTRIBUTES event"):
        apply_event_to_graph(event, graph)

# This old test is covered by the new parametrized one below for the "Missing 'attributes' key" case.
# def test_apply_update_node_attributes_missing_attributes(graph: MockGraph):
#     """Test error for UPDATE_NODE_ATTRIBUTES if 'attributes' is missing."""
#     node_id = "node1"
#     graph.add_node(node_id, {"name": "Initial Name"})
#     event = Event(
#         event_type="UPDATE_NODE_ATTRIBUTES",
#         timestamp=int(time.time()),
#         payload={"node_id": node_id} # Missing attributes field
#     )
#     with pytest.raises(ProcessingError, match="Missing 'attributes' in payload for UPDATE_NODE_ATTRIBUTES event"):
#         apply_event_to_graph(event, graph)

@pytest.mark.parametrize(
    "attributes_payload, expected_error_message_part",
    [
        # Case 1: "attributes" key completely missing from payload
        ({"node_id": "node1"}, "Missing 'attributes' key in payload"),

        # Case 2: "attributes" key present, but value is None
        # This will be caught by "must be a dictionary"
        ({"node_id": "node1", "attributes": None}, "'attributes' must be a dictionary"),

        # Case 3: "attributes" key present, but value is not a dictionary
        ({"node_id": "node1", "attributes": "not-a-dict"}, "'attributes' must be a dictionary"),

        # Case 4: "attributes" key present, value is an empty dictionary
        ({"node_id": "node1", "attributes": {}}, "'attributes' dictionary cannot be empty"),
    ]
)
def test_apply_update_node_attributes_invalid_attributes_payload(
    graph: MockGraph, attributes_payload: dict, expected_error_message_part: str
):
    """
    Tests UPDATE_NODE_ATTRIBUTES with various invalid 'attributes' payloads,
    checking against the refined validation logic.
    """
    node_id = "node1" # Common node_id for these tests

    # Ensure the node exists for update tests, unless the error occurs before that check
    if "Node 'node1' does not exist" not in expected_error_message_part:
         if not graph.node_exists(node_id) and \
            "Missing 'attributes' key" not in expected_error_message_part and \
            "'attributes' must be a dictionary" not in expected_error_message_part and \
            "'attributes' dictionary cannot be empty" not in expected_error_message_part :
            graph.add_node(node_id, {"initial_name": "Test"})

    event_payload = attributes_payload.copy()
    if "node_id" not in event_payload: # Ensure node_id from parametrization is used if provided, else default
        event_payload["node_id"] = node_id


    event = Event(
        event_type="UPDATE_NODE_ATTRIBUTES",
        timestamp=int(time.time()),
        payload=event_payload
    )

    with pytest.raises(ProcessingError) as excinfo:
        apply_event_to_graph(event, graph)

    assert expected_error_message_part in str(excinfo.value)

def test_apply_unknown_event_type(graph: MockGraph):
    """Test error when an unknown event_type is encountered."""
    event = Event(
        event_type="UNKNOWN_EVENT_TYPE",
        timestamp=int(time.time()),
        payload={"data": "some_data"}
    )
    with pytest.raises(ProcessingError, match="Unknown event_type 'UNKNOWN_EVENT_TYPE'"):
        apply_event_to_graph(event, graph)

# --- apply_event_to_graph: CREATE_EDGE tests ---
def test_apply_create_edge_event_success(graph: MockGraph):
    """Test successfully applying a CREATE_EDGE event."""
    graph.add_node("source_node", {})
    graph.add_node("target_node", {})

    # Assuming parse_event handles creating the Event object correctly for this test
    # For apply_event_to_graph tests, we typically construct Event objects directly for clarity
    event = Event(
        event_type="CREATE_EDGE",
        timestamp=int(time.time()),
        node_id="source_node",
        target_node_id="target_node",
        label="RELATES_TO",
        payload={} # Explicitly empty for clarity, though parse_event would default
    )

    apply_event_to_graph(event, graph)

    # Verify edge was added (MockGraph stores edges as list of tuples)
    assert ("source_node", "target_node", "RELATES_TO") in graph.get_all_edges()

def test_apply_create_edge_event_missing_source_node(graph: MockGraph):
    """Test CREATE_EDGE when source node does not exist (error from adapter)."""
    graph.add_node("target_node", {}) # Target exists
    event = Event(
        event_type="CREATE_EDGE",
        timestamp=int(time.time()),
        node_id="missing_source",
        target_node_id="target_node",
        label="LINKS_TO",
        payload={}
    )
    with pytest.raises(ProcessingError, match="Both source node 'missing_source' and target node 'target_node' must exist"):
        apply_event_to_graph(event, graph)

def test_apply_create_edge_event_missing_target_node(graph: MockGraph):
    """Test CREATE_EDGE when target node does not exist (error from adapter)."""
    graph.add_node("source_node", {}) # Source exists
    event = Event(
        event_type="CREATE_EDGE",
        timestamp=int(time.time()),
        node_id="source_node",
        target_node_id="missing_target",
        label="CONNECTS_TO",
        payload={}
    )
    with pytest.raises(ProcessingError, match="Both source node 'source_node' and target node 'missing_target' must exist"):
        apply_event_to_graph(event, graph)

def test_apply_create_edge_event_invalid_field_types_propagates_error(graph: MockGraph):
    """
    Test CREATE_EDGE when event fields (node_id, target_node_id, label) are not strings.
    This tests the defensive checks in apply_event_to_graph.
    """
    graph.add_node("source_node", {})
    graph.add_node("target_node", {})

    # Example: target_node_id is int
    event_bad_target_type = Event(
        event_type="CREATE_EDGE",
        timestamp=int(time.time()),
        node_id="source_node",
        target_node_id=123,  # type: ignore[arg-type]
        label="LINKS_TO",
        payload={},
    )
    with pytest.raises(ProcessingError, match="Invalid event structure for CREATE_EDGE"):
        apply_event_to_graph(event_bad_target_type, graph)

    # Example: label is int
    event_bad_label_type = Event(
        event_type="CREATE_EDGE",
        timestamp=int(time.time()),
        node_id="source_node",
        target_node_id="target_node",
        label=456,  # type: ignore[arg-type]
        payload={},
    )
    with pytest.raises(ProcessingError, match="Invalid event structure for CREATE_EDGE"):
        apply_event_to_graph(event_bad_label_type, graph)


# --- apply_event_to_graph: DELETE_EDGE tests ---
def test_apply_delete_edge_event_success(graph: MockGraph):
    """Test successfully applying a DELETE_EDGE event."""
    graph.add_node("s_node", {})
    graph.add_node("t_node", {})
    graph.add_edge("s_node", "t_node", "TO_DELETE")
    assert ("s_node", "t_node", "TO_DELETE") in graph.get_all_edges() # Verify setup

    event = Event(
        event_type="DELETE_EDGE",
        timestamp=int(time.time()),
        node_id="s_node",
        target_node_id="t_node",
        label="TO_DELETE",
        payload={}
    )
    apply_event_to_graph(event, graph)
    assert ("s_node", "t_node", "TO_DELETE") not in graph.get_all_edges()

def test_apply_delete_edge_event_edge_not_exist(graph: MockGraph):
    """Test DELETE_EDGE when the specified edge does not exist (error from adapter)."""
    graph.add_node("s_node", {})
    graph.add_node("t_node", {})
    # Edge is never added

    event = Event(
        event_type="DELETE_EDGE",
        timestamp=int(time.time()),
        node_id="s_node",
        target_node_id="t_node",
        label="NON_EXISTENT",
        payload={}
    )
    edge_tuple = ("s_node", "t_node", "NON_EXISTENT")
    with pytest.raises(ProcessingError, match=re.escape(f"Edge {edge_tuple} does not exist and cannot be deleted.")):
        apply_event_to_graph(event, graph)

def test_apply_delete_edge_event_invalid_field_types_propagates_error(graph: MockGraph):
    """
    Test DELETE_EDGE when event fields (node_id, target_node_id, label) are not strings.
    This tests the defensive checks in apply_event_to_graph.
    """
    event_bad_label_type = Event(
        event_type="DELETE_EDGE",
        timestamp=int(time.time()),
        node_id="s",
        target_node_id="t",
        label=123,  # type: ignore[arg-type]
        payload={},
    )
    with pytest.raises(ProcessingError, match="Invalid event structure for DELETE_EDGE"):
        apply_event_to_graph(event_bad_label_type, graph)
