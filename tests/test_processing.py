# tests/test_processing.py
import pytest
import time
import re
from ume import (
    DEFAULT_SCHEMA_MANAGER,
    Event,
    EventType,
    PersistentGraph,
    apply_event_to_graph,
    ProcessingError,
    parse_event,
)


@pytest.fixture
def graph() -> PersistentGraph:
    """Pytest fixture to provide a clean in-memory PersistentGraph instance."""
    return PersistentGraph(":memory:")


def test_apply_create_node_event_success(graph: PersistentGraph):
    """Test successfully creating a new node."""
    event_id = "event1"
    node_id = "node1"
    attributes = {"name": "Test Node", "value": 100, "type": "User"}
    event = Event(
        event_id=event_id,
        event_type=EventType.CREATE_NODE,
        timestamp=int(time.time()),
        node_id=node_id,
        payload={"node_id": node_id, "attributes": attributes},
    )
    apply_event_to_graph(event, graph)
    assert graph.node_exists(node_id)
    stored = graph.get_node(node_id)
    assert stored == {**attributes, "tokens": ["Test", "Node"]}
    assert graph.node_count == 1


def test_create_node_adds_tokens_from_text(graph: PersistentGraph) -> None:
    """CREATE_NODE with a text field should store tokens."""
    node_id = "node_text"
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=int(time.time()),
        node_id=node_id,
        payload={"node_id": node_id, "attributes": {"text": "Alpha Beta"}},
    )
    apply_event_to_graph(event, graph)
    assert graph.get_node(node_id) == {
        "text": "Alpha Beta",
        "tokens": ["Alpha", "Beta"],
    }


def test_apply_create_node_event_no_attributes(graph: PersistentGraph):
    """Test successfully creating a new node with no initial attributes."""
    node_id = "node_no_attr"
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=int(time.time()),
        node_id=node_id,
        payload={"node_id": node_id},  # Attributes are optional in payload for create
    )
    apply_event_to_graph(event, graph)
    assert graph.node_exists(node_id)
    assert graph.get_node(node_id) == {}  # Should be an empty dict


def test_apply_create_node_event_already_exists(graph: PersistentGraph):
    """Test error when trying to create a node that already exists."""
    node_id = "node1"
    graph.add_node(node_id, {"name": "Initial Node"})  # Pre-existing node
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=int(time.time()),
        node_id=node_id,
        payload={
            "node_id": node_id,
            "attributes": {"name": "New Node", "type": "User"},
        },
    )
    with pytest.raises(ProcessingError, match=f"Node '{node_id}' already exists"):
        apply_event_to_graph(event, graph)


def test_apply_create_node_missing_node_id(graph: PersistentGraph):
    """Test error when 'node_id' is missing in payload for CREATE_NODE."""
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=int(time.time()),
        payload={"attributes": {"name": "Test Node"}},
    )
    with pytest.raises(
        ProcessingError, match="Missing 'node_id' in event for CREATE_NODE event"
    ):
        apply_event_to_graph(event, graph)


def test_apply_create_node_invalid_node_id_type(graph: PersistentGraph):
    """Test error when 'node_id' is not a string for CREATE_NODE."""
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=int(time.time()),
        node_id=123,  # type: ignore[arg-type]
        payload={"node_id": 123, "attributes": {"name": "Test Node"}},  # node_id is int
    )
    with pytest.raises(
        ProcessingError, match="'node_id' must be a string for CREATE_NODE event"
    ):
        apply_event_to_graph(event, graph)


def test_apply_update_node_attributes_success(graph: PersistentGraph):
    """Test successfully updating attributes of an existing node."""
    node_id = "node1"
    initial_attrs = {"name": "Initial Name", "status": "active"}
    updated_attrs = {"status": "inactive", "version": 2}
    expected_final_attrs = {"name": "Initial Name", "status": "inactive", "version": 2}

    graph.add_node(node_id, initial_attrs)
    event = Event(
        event_type=EventType.UPDATE_NODE_ATTRIBUTES,
        timestamp=int(time.time()),
        node_id=node_id,
        payload={"node_id": node_id, "attributes": updated_attrs},
    )
    apply_event_to_graph(event, graph)
    assert graph.get_node(node_id) == expected_final_attrs


def test_update_node_adds_tokens(graph: PersistentGraph) -> None:
    """Updating with text attributes should store tokens."""
    node_id = "node_tokens"
    graph.add_node(node_id, {})
    event = Event(
        event_type=EventType.UPDATE_NODE_ATTRIBUTES,
        timestamp=int(time.time()),
        node_id=node_id,
        payload={"node_id": node_id, "attributes": {"content": "Hello world"}},
    )
    apply_event_to_graph(event, graph)
    assert graph.get_node(node_id) == {"content": "Hello world", "tokens": ["Hello", "world"]}


def test_apply_update_node_attributes_node_not_exists(graph: PersistentGraph):
    """Test error when trying to update attributes of a non-existent node."""
    node_id = "node_not_found"
    event = Event(
        event_type=EventType.UPDATE_NODE_ATTRIBUTES,
        timestamp=int(time.time()),
        node_id=node_id,
        payload={"node_id": node_id, "attributes": {"name": "Updated Name"}},
    )
    with pytest.raises(
        ProcessingError, match=re.escape(f"Node '{node_id}' not found for update.")
    ):
        apply_event_to_graph(event, graph)


def test_apply_update_node_attributes_missing_node_id(graph: PersistentGraph):
    """Test error for UPDATE_NODE_ATTRIBUTES if 'node_id' is missing."""
    event = Event(
        event_type=EventType.UPDATE_NODE_ATTRIBUTES,
        timestamp=int(time.time()),
        payload={"attributes": {"name": "Updated Name"}},
    )
    with pytest.raises(
        ProcessingError,
        match="Missing 'node_id' in event for UPDATE_NODE_ATTRIBUTES event",
    ):
        apply_event_to_graph(event, graph)


# This old test is covered by the new parametrized one below for the "Missing 'attributes' key" case.
# def test_apply_update_node_attributes_missing_attributes(graph: PersistentGraph):
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
        (
            {"node_id": "node1", "attributes": "not-a-dict"},
            "'attributes' must be a dictionary",
        ),
        # Case 4: "attributes" key present, value is an empty dictionary
        (
            {"node_id": "node1", "attributes": {}},
            "'attributes' dictionary cannot be empty",
        ),
    ],
)
def test_apply_update_node_attributes_invalid_attributes_payload(
    graph: PersistentGraph, attributes_payload: dict, expected_error_message_part: str
):
    """
    Tests UPDATE_NODE_ATTRIBUTES with various invalid 'attributes' payloads,
    checking against the refined validation logic.
    """
    node_id = "node1"  # Common node_id for these tests

    # Ensure the node exists for update tests, unless the error occurs before that check
    if "Node 'node1' does not exist" not in expected_error_message_part:
        if (
            not graph.node_exists(node_id)
            and "Missing 'attributes' key" not in expected_error_message_part
            and "'attributes' must be a dictionary" not in expected_error_message_part
            and "'attributes' dictionary cannot be empty"
            not in expected_error_message_part
        ):
            graph.add_node(node_id, {"initial_name": "Test"})

    event_payload = attributes_payload.copy()
    if (
        "node_id" not in event_payload
    ):  # Ensure node_id from parametrization is used if provided, else default
        event_payload["node_id"] = node_id

    event = Event(
        event_type=EventType.UPDATE_NODE_ATTRIBUTES,
        timestamp=int(time.time()),
        node_id=event_payload.get("node_id"),
        payload=event_payload,
    )

    with pytest.raises(ProcessingError) as excinfo:
        apply_event_to_graph(event, graph)

    assert expected_error_message_part in str(excinfo.value)


def test_apply_unknown_event_type(graph: PersistentGraph):
    """Test error when an unknown event_type is encountered."""
    event = Event(
        event_type="UNKNOWN_EVENT_TYPE",
        timestamp=int(time.time()),
        payload={"data": "some_data"},
    )
    with pytest.raises(
        ProcessingError, match="Unknown event_type 'UNKNOWN_EVENT_TYPE'"
    ):
        apply_event_to_graph(event, graph)


# --- apply_event_to_graph: CREATE_EDGE tests ---
def test_apply_create_edge_event_success(graph: PersistentGraph):
    """Test successfully applying a CREATE_EDGE event."""
    graph.add_node("source_node", {})
    graph.add_node("target_node", {})

    # Assuming parse_event handles creating the Event object correctly for this test
    # For apply_event_to_graph tests, we typically construct Event objects directly for clarity
    event = Event(
        event_type=EventType.CREATE_EDGE,
        timestamp=int(time.time()),
        node_id="source_node",
        target_node_id="target_node",
        label="TAGGED_AS",
        payload={},  # Explicitly empty for clarity, though parse_event would default
    )

    apply_event_to_graph(event, graph)

    # Verify edge was added (PersistentGraph stores edges as list of tuples)
    edges = graph.get_all_edges()
    assert len(edges) == 1
    src, tgt, label, attrs = edges[0]
    assert (src, tgt, label) == ("source_node", "target_node", "TAGGED_AS")
    expected_version = DEFAULT_SCHEMA_MANAGER.get_edge_version("TAGGED_AS")
    assert attrs == {"schema_version": expected_version}


def test_apply_create_edge_event_permission_attributes(graph: PersistentGraph) -> None:
    """Explicit permission metadata should be preserved on the stored edge."""
    graph.add_node("owner", {})
    graph.add_node("resource", {})

    event = Event(
        event_type=EventType.CREATE_EDGE,
        timestamp=int(time.time()),
        node_id="owner",
        target_node_id="resource",
        label="OWNED_BY",
        payload={"attributes": {"permission_level": "editor", "note": "custom"}},
    )

    apply_event_to_graph(event, graph)

    edges = graph.get_all_edges()
    assert len(edges) == 1
    source, target, label, attrs = edges[0]
    assert (source, target, label) == ("owner", "resource", "OWNED_BY")
    assert attrs["permission_level"] == "editor"
    assert attrs["note"] == "custom"
    expected_version = DEFAULT_SCHEMA_MANAGER.get_edge_version("OWNED_BY")
    assert attrs["schema_version"] == expected_version


def test_apply_create_edge_event_permission_defaults(graph: PersistentGraph) -> None:
    """Permissioned edges without metadata should fall back to schema defaults."""
    graph.add_node("owner", {})
    graph.add_node("shared", {})

    event = Event(
        event_type=EventType.CREATE_EDGE,
        timestamp=int(time.time()),
        node_id="owner",
        target_node_id="shared",
        label="SHARED_WITH",
        payload={},
    )

    apply_event_to_graph(event, graph)

    edges = graph.get_all_edges()
    assert len(edges) == 1
    _, _, label, attrs = edges[0]
    assert label == "SHARED_WITH"
    expected_version = DEFAULT_SCHEMA_MANAGER.get_edge_version("SHARED_WITH")
    assert attrs["permission_level"] == "viewer"
    assert attrs["schema_version"] == expected_version


def test_apply_create_edge_event_invalid_permission_level(graph: PersistentGraph) -> None:
    """Invalid permission metadata should raise a processing error."""
    graph.add_node("owner", {})
    graph.add_node("resource", {})

    event = Event(
        event_type=EventType.CREATE_EDGE,
        timestamp=int(time.time()),
        node_id="owner",
        target_node_id="resource",
        label="OWNED_BY",
        payload={"attributes": {"permission_level": "invalid"}},
    )

    with pytest.raises(
        ProcessingError,
        match="Invalid permission_level 'invalid' for edge label 'OWNED_BY'",
    ):
        apply_event_to_graph(event, graph)


def test_apply_create_edge_event_missing_source_node(graph: PersistentGraph):
    """Test CREATE_EDGE when source node does not exist (error from adapter)."""
    graph.add_node("target_node", {})  # Target exists
    event = Event(
        event_type=EventType.CREATE_EDGE,
        timestamp=int(time.time()),
        node_id="missing_source",
        target_node_id="target_node",
        label="TAGGED_AS",
        payload={},
    )
    with pytest.raises(
        ProcessingError,
        match="Both source node 'missing_source' and target node 'target_node' must exist",
    ):
        apply_event_to_graph(event, graph)


def test_apply_create_edge_event_missing_target_node(graph: PersistentGraph):
    """Test CREATE_EDGE when target node does not exist (error from adapter)."""
    graph.add_node("source_node", {})  # Source exists
    event = Event(
        event_type=EventType.CREATE_EDGE,
        timestamp=int(time.time()),
        node_id="source_node",
        target_node_id="missing_target",
        label="TAGGED_AS",
        payload={},
    )
    with pytest.raises(
        ProcessingError,
        match="Both source node 'source_node' and target node 'missing_target' must exist",
    ):
        apply_event_to_graph(event, graph)


def test_apply_create_edge_event_invalid_field_types_propagates_error(
    graph: PersistentGraph,
):
    """
    Test CREATE_EDGE when event fields (node_id, target_node_id, label) are not strings.
    This tests the defensive checks in apply_event_to_graph.
    """
    graph.add_node("source_node", {})
    graph.add_node("target_node", {})

    # Example: target_node_id is int
    event_bad_target_type = Event(
        event_type=EventType.CREATE_EDGE,
        timestamp=int(time.time()),
        node_id="source_node",
        target_node_id=123,  # type: ignore[arg-type]
        label="TAGGED_AS",
        payload={},
    )
    with pytest.raises(
        ProcessingError, match="Invalid event structure for CREATE_EDGE"
    ):
        apply_event_to_graph(event_bad_target_type, graph)

    # Example: label is int
    event_bad_label_type = Event(
        event_type=EventType.CREATE_EDGE,
        timestamp=int(time.time()),
        node_id="source_node",
        target_node_id="target_node",
        label=456,  # type: ignore[arg-type]
        payload={},
    )
    with pytest.raises(
        ProcessingError, match="Invalid event structure for CREATE_EDGE"
    ):
        apply_event_to_graph(event_bad_label_type, graph)


# --- apply_event_to_graph: DELETE_EDGE tests ---
def test_apply_delete_edge_event_success(graph: PersistentGraph):
    """Test successfully applying a DELETE_EDGE event."""
    graph.add_node("s_node", {})
    graph.add_node("t_node", {})
    graph.add_edge("s_node", "t_node", "TO_DELETE")
    assert ("s_node", "t_node", "TO_DELETE", {}) in graph.get_all_edges()  # Verify setup

    event = Event(
        event_type=EventType.DELETE_EDGE,
        timestamp=int(time.time()),
        node_id="s_node",
        target_node_id="t_node",
        label="TO_DELETE",
        payload={},
    )
    apply_event_to_graph(event, graph)
    assert ("s_node", "t_node", "TO_DELETE", {}) not in graph.get_all_edges()


def test_apply_delete_edge_event_edge_not_exist(graph: PersistentGraph):
    """Test DELETE_EDGE when the specified edge does not exist (error from adapter)."""
    graph.add_node("s_node", {})
    graph.add_node("t_node", {})
    # Edge is never added

    event = Event(
        event_type=EventType.DELETE_EDGE,
        timestamp=int(time.time()),
        node_id="s_node",
        target_node_id="t_node",
        label="NON_EXISTENT",
        payload={},
    )
    edge_tuple = ("s_node", "t_node", "NON_EXISTENT")
    expected = re.escape(f"Edge {edge_tuple} does not exist and cannot be deleted.")
    with pytest.raises(ProcessingError, match=expected):
        apply_event_to_graph(event, graph)


def test_apply_delete_edge_event_invalid_field_types_propagates_error(
    graph: PersistentGraph,
):
    """
    Test DELETE_EDGE when event fields (node_id, target_node_id, label) are not strings.
    This tests the defensive checks in apply_event_to_graph.
    """
    event_bad_label_type = Event(
        event_type=EventType.DELETE_EDGE,
        timestamp=int(time.time()),
        node_id="s",
        target_node_id="t",
        label=123,  # type: ignore[arg-type]
        payload={},  # label is int
    )
    with pytest.raises(
        ProcessingError, match="Invalid event structure for DELETE_EDGE"
    ):
        apply_event_to_graph(event_bad_label_type, graph)


def test_apply_research_job_started_creates_node(graph: PersistentGraph) -> None:
    event = Event(
        event_type=EventType.RESEARCH_JOB_STARTED,
        timestamp=int(time.time()),
        node_id="job1",
        payload={"node_id": "job1", "attributes": {"status": "started"}},
    )
    apply_event_to_graph(event, graph)
    assert graph.node_exists("job1")
    assert graph.get_node("job1") == {"status": "started"}


def test_apply_data_source_queried_adds_edge(graph: PersistentGraph, monkeypatch: pytest.MonkeyPatch) -> None:
    from ume.graph_schema import GraphSchema, EdgeLabel
    from ume.schema_manager import DEFAULT_SCHEMA_MANAGER
    schema = GraphSchema(version="1.0.0", edge_labels={"RELATES_TO": EdgeLabel("RELATES_TO", "1.0.0")})
    monkeypatch.setattr(DEFAULT_SCHEMA_MANAGER, "get_schema", lambda v: schema)
    graph.add_node("job1", {})
    graph.add_node("ds1", {})
    event = Event(
        event_type=EventType.DATA_SOURCE_QUERIED,
        timestamp=int(time.time()),
        node_id="job1",
        target_node_id="ds1",
        label="RELATES_TO",
        payload={},
    )
    apply_event_to_graph(event, graph)
    edges = graph.get_all_edges()
    assert len(edges) == 1
    src, tgt, label, attrs = edges[0]
    assert (src, tgt, label) == ("job1", "ds1", "RELATES_TO")
    assert attrs == {"schema_version": "1.0.0"}


def test_apply_entity_discovered_creates_node_and_edge(graph: PersistentGraph, monkeypatch: pytest.MonkeyPatch) -> None:
    from ume.graph_schema import GraphSchema, EdgeLabel
    from ume.schema_manager import DEFAULT_SCHEMA_MANAGER
    schema = GraphSchema(version="1.0.0", edge_labels={"RELATES_TO": EdgeLabel("RELATES_TO", "1.0.0")})
    monkeypatch.setattr(DEFAULT_SCHEMA_MANAGER, "get_schema", lambda v: schema)
    graph.add_node("job1", {})
    event = Event(
        event_type=EventType.ENTITY_DISCOVERED,
        timestamp=int(time.time()),
        node_id="job1",
        target_node_id="ent1",
        label="RELATES_TO",
        payload={"attributes": {"name": "E1"}},
    )
    apply_event_to_graph(event, graph)
    assert graph.node_exists("ent1")
    assert graph.get_node("ent1") == {"name": "E1", "tokens": ["E1"]}
    edges = graph.get_all_edges()
    assert len(edges) == 1
    src, tgt, label, attrs = edges[0]
    assert (src, tgt, label) == ("job1", "ent1", "RELATES_TO")
    assert attrs == {"name": "E1", "schema_version": "1.0.0"}


def test_apply_document_archived_updates_node(graph: PersistentGraph) -> None:
    graph.add_node("doc1", {"title": "D"})
    event = Event(
        event_type=EventType.DOCUMENT_ARCHIVED,
        timestamp=int(time.time()),
        node_id="doc1",
        payload={"node_id": "doc1", "attributes": {}},
    )
    apply_event_to_graph(event, graph)
    assert graph.get_node("doc1") == {"title": "D", "archived": True}


def test_apply_create_node_parsed_backward_compat_payload_node_id(graph: PersistentGraph) -> None:
    event = parse_event(
        {
            "eventType": EventType.CREATE_NODE.value,
            "timestamp": int(time.time()),
            "payload": {"node_id": "legacy-node", "attributes": {"name": "Legacy"}},
        }
    )
    apply_event_to_graph(event, graph)
    assert graph.node_exists("legacy-node")


def test_apply_create_node_prefers_top_level_node_id(graph: PersistentGraph) -> None:
    event = parse_event(
        {
            "eventType": EventType.CREATE_NODE.value,
            "timestamp": int(time.time()),
            "node_id": "node-top",
            "payload": {"node_id": "node-top", "attributes": {"name": "Top"}},
        }
    )
    apply_event_to_graph(event, graph)
    assert graph.node_exists("node-top")
