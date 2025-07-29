# tests/test_event.py
import pytest
import time
from ume import Event, EventType, parse_event, EventError  # EventType constants


def test_parse_event_valid():
    """Test parsing a valid event dictionary."""
    timestamp_now = int(time.time())
    event_data = {
        "eventId": "test-id-123",
        "eventType": "test_event",
        "timestamp": timestamp_now,
        "payload": {"key": "value", "num": 123},
        "sourceService": "test_source",
        "correlationId": "c123",
        "subjectEntity": {"id": "u1", "type": "user"},
    }
    event = parse_event(event_data)
    assert isinstance(event, Event)
    assert event.event_id == "test-id-123"
    assert event.event_type == "test_event"
    assert event.timestamp == timestamp_now
    assert event.payload == {"key": "value", "num": 123}
    assert event.source == "test_source"
    assert event.correlation_id == "c123"
    assert event.subject_entity == {"id": "u1", "type": "user"}


def test_parse_event_minimal_valid():
    """Test parsing a minimal valid event dictionary (event_id and source generated)."""
    timestamp_now = int(time.time())
    event_data = {
        "eventType": "minimal_event",
        "timestamp": timestamp_now,
        "payload": {"data": "minimal_data"},
    }
    event = parse_event(event_data)
    assert isinstance(event, Event)
    assert event.event_type == "minimal_event"
    assert event.timestamp == timestamp_now
    assert event.payload == {"data": "minimal_data"}
    assert event.event_id is not None  # Should be auto-generated
    assert isinstance(event.event_id, str)
    assert event.source is None  # Should default to None
    assert event.correlation_id is None
    assert event.subject_entity is None
    assert event.source_service is None


def test_parse_event_custom_type():
    """Ensure custom event types parse without strict checks."""
    timestamp_now = int(time.time())
    data = {
        "eventType": "document.artifact.archived",
        "timestamp": timestamp_now,
        "payload": {"archive": True},
    }
    event = parse_event(data)
    assert event.event_type == "document.artifact.archived"
    assert event.payload == {"archive": True}


def test_parse_event_custom_type_minimal():
    """Unknown event types should parse with minimal required fields."""
    ts = int(time.time())
    data = {"eventType": "document.artifact.archived", "timestamp": ts}
    event = parse_event(data)
    assert event.event_type == "document.artifact.archived"
    assert event.timestamp == ts
    assert event.payload == {}


@pytest.mark.parametrize(
    "event_type, extra_data",
    [
        (EventType.CREATE_EDGE, {"target_node_id": "t1", "label": "LINKS_TO"}),
        (EventType.DELETE_EDGE, {"target_node_id": "t2", "label": "REMOVES_LINK"}),
    ],
)
def test_parse_event_valid_edge_events(event_type: EventType, extra_data: dict):
    """Test parsing valid CREATE_EDGE and DELETE_EDGE events."""
    timestamp_now = int(time.time())
    event_data = {
        "eventType": event_type.value,
        "timestamp": timestamp_now,
        "node_id": "s1",  # Source node
        **extra_data,  # Adds target_node_id and label
        # payload is optional for these, parse_event defaults to {}
    }
    event = parse_event(event_data)
    assert isinstance(event, Event)
    assert event.event_type == event_type
    assert event.timestamp == timestamp_now
    assert event.node_id == "s1"
    assert event.target_node_id == extra_data["target_node_id"]
    assert event.label == extra_data["label"]
    assert event.payload == {}  # Default empty payload


# The following tests are now covered by test_parse_event_invalid_inputs:
# - test_parse_event_missing_required_field
# - test_parse_event_missing_multiple_required_fields
# - test_parse_event_invalid_type_for_event_type
# - test_parse_event_invalid_type_for_timestamp
# - test_parse_event_invalid_type_for_payload


@pytest.mark.parametrize(
    "bad_input, expected_message_part",
    [
        # Case 1: Missing all required fields
        ({}, "Missing required event field: eventType"),
        # Case 2: Missing 'event_type'
        ({"timestamp": 123, "payload": {}}, "Missing required event field: eventType"),
        # Case 3: Missing 'timestamp'
        (
            {"eventType": "test", "payload": {}},
            "Missing required event field: timestamp",
        ),
        # Case 4: Missing 'payload' for CREATE_NODE
        (
            {"eventType": "CREATE_NODE", "timestamp": 123, "node_id": "n1"},
            "Missing required field 'payload' for CREATE_NODE event.",
        ),
        # Case 5: Invalid type for 'eventType' (int instead of str)
        (
            {"eventType": 123, "timestamp": int(time.time()), "payload": {}},
            "Invalid type for 'eventType'",
        ),
        # Case 6: Invalid type for 'timestamp' (str instead of int)
        (
            {"eventType": "test", "timestamp": "not-an-int", "payload": {}},
            "Invalid type for 'timestamp'",
        ),
        # Case 7: Invalid type for 'payload' (str instead of dict)
        (
            {
                "eventType": "CREATE_EDGE",
                "timestamp": int(time.time()),
                "node_id": "s1",
                "target_node_id": "t1",
                "label": "L",
                "payload": "not-a-dict",
            },
            "Invalid type for 'payload' in CREATE_EDGE event (if provided): expected dict",
        ),
        # New cases for CREATE_EDGE
        # CREATE_EDGE missing target_node_id
        (
            {
                "eventType": "CREATE_EDGE",
                "timestamp": int(time.time()),
                "node_id": "s1",
                "label": "L",
            },
            "Missing required fields for CREATE_EDGE event: target_node_id",
        ),
        # CREATE_EDGE missing label
        (
            {
                "eventType": "CREATE_EDGE",
                "timestamp": int(time.time()),
                "node_id": "s1",
                "target_node_id": "t1",
            },
            "Missing required fields for CREATE_EDGE event: label",
        ),
        # CREATE_EDGE target_node_id not string
        (
            {
                "eventType": "CREATE_EDGE",
                "timestamp": int(time.time()),
                "node_id": "s1",
                "target_node_id": 123,
                "label": "L",
            },
            "Invalid type for 'target_node_id' in CREATE_EDGE event",
        ),
        # CREATE_EDGE label not string
        (
            {
                "eventType": "CREATE_EDGE",
                "timestamp": int(time.time()),
                "node_id": "s1",
                "target_node_id": "t1",
                "label": 123,
            },
            "Invalid type for 'label' in CREATE_EDGE event",
        ),
        # CREATE_EDGE node_id (source) missing
        (
            {
                "eventType": "CREATE_EDGE",
                "timestamp": int(time.time()),
                "target_node_id": "t1",
                "label": "L",
            },
            "Missing required fields for CREATE_EDGE event: node_id",
        ),
        # CREATE_EDGE with payload of wrong type
        (
            {
                "eventType": "CREATE_EDGE",
                "timestamp": int(time.time()),
                "node_id": "s1",
                "target_node_id": "t1",
                "label": "L",
                "payload": "not-a-dict",
            },
            "Invalid type for 'payload' in CREATE_EDGE event (if provided): expected dict",
        ),
        # New cases for DELETE_EDGE
        # DELETE_EDGE missing target_node_id
        (
            {
                "eventType": "DELETE_EDGE",
                "timestamp": int(time.time()),
                "node_id": "s1",
                "label": "L",
            },
            "Missing required fields for DELETE_EDGE event: target_node_id",
        ),
        # DELETE_EDGE missing label
        (
            {
                "eventType": "DELETE_EDGE",
                "timestamp": int(time.time()),
                "node_id": "s1",
                "target_node_id": "t1",
            },
            "Missing required fields for DELETE_EDGE event: label",
        ),
        # DELETE_EDGE target_node_id not string
        (
            {
                "eventType": "DELETE_EDGE",
                "timestamp": int(time.time()),
                "node_id": "s1",
                "target_node_id": 123,
                "label": "L",
            },
            "Invalid type for 'target_node_id' in DELETE_EDGE event",
        ),
        # DELETE_EDGE label not string
        (
            {
                "eventType": "DELETE_EDGE",
                "timestamp": int(time.time()),
                "node_id": "s1",
                "target_node_id": "t1",
                "label": 123,
            },
            "Invalid type for 'label' in DELETE_EDGE event",
        ),
        # DELETE_EDGE node_id (source) missing
        (
            {
                "eventType": "DELETE_EDGE",
                "timestamp": int(time.time()),
                "target_node_id": "t1",
                "label": "L",
            },
            "Missing required fields for DELETE_EDGE event: node_id",
        ),
        # DELETE_EDGE with payload of wrong type
        (
            {
                "eventType": "DELETE_EDGE",
                "timestamp": int(time.time()),
                "node_id": "s1",
                "target_node_id": "t1",
                "label": "L",
                "payload": "not-a-dict",
            },
            "Invalid type for 'payload' in DELETE_EDGE event (if provided): expected dict",
        ),
        # Cases for CREATE_NODE / UPDATE_NODE_ATTRIBUTES payload validation (if payload key exists but is not dict)
        (
            {
                "eventType": "CREATE_NODE",
                "timestamp": int(time.time()),
                "node_id": "n1",
                "payload": "not-a-dict",
            },
            "Invalid type for 'payload' in CREATE_NODE event: expected dict",
        ),
        (
            {
                "eventType": "UPDATE_NODE_ATTRIBUTES",
                "timestamp": int(time.time()),
                "node_id": "n1",
                "payload": "not-a-dict",
            },
            "Invalid type for 'payload' in UPDATE_NODE_ATTRIBUTES event: expected dict",
        ),
        # Cases for CREATE_NODE / UPDATE_NODE_ATTRIBUTES missing payload key
        (
            {
                "eventType": "CREATE_NODE",
                "timestamp": int(time.time()),
                "node_id": "n1",
            },
            "Missing required field 'payload' for CREATE_NODE event",
        ),
        (
            {
                "eventType": "UPDATE_NODE_ATTRIBUTES",
                "timestamp": int(time.time()),
                "node_id": "n1",
            },
            "Missing required field 'payload' for UPDATE_NODE_ATTRIBUTES event",
        ),
        # event_id present but wrong type
        (
            {
                "eventType": "test",
                "timestamp": int(time.time()),
                "payload": {},
                "eventId": 123,
            },
            "Invalid type for 'eventId'",
        ),
        (
            {
                "eventType": "test",
                "timestamp": int(time.time()),
                "payload": {},
                "correlationId": 1,
            },
            "Invalid type for 'correlationId'",
        ),
        (
            {
                "eventType": "test",
                "timestamp": int(time.time()),
                "payload": {},
                "subjectEntity": 1,
            },
            "Invalid type for 'subjectEntity'",
        ),
        (
            {
                "eventType": "test",
                "timestamp": int(time.time()),
                "payload": {},
                "sourceService": 1,
            },
            "Invalid type for 'sourceService'",
        ),
    ],
)
def test_parse_event_invalid_inputs(bad_input: dict, expected_message_part: str):
    """
    Tests parse_event with various malformed input dictionaries,
    expecting an EventError.
    """
    with pytest.raises(EventError) as excinfo:
        parse_event(bad_input)
    assert expected_message_part in str(excinfo.value)


def test_event_creation_default_id():
    """Test that Event dataclass generates a default UUID for event_id."""
    event = Event(event_type="test", timestamp=int(time.time()), payload={})
    assert event.event_id is not None
    assert isinstance(event.event_id, str)
    # A simple check for UUID-like structure (36 chars, with hyphens)
    assert len(event.event_id) == 36
    assert "-" in event.event_id


def test_parse_event_logs_error(caplog):
    """Ensure parse_event logs an error when required fields are missing."""
    with caplog.at_level("ERROR"):
        with pytest.raises(EventError):
            parse_event({})
        assert any(
            "Missing required event field: eventType" in rec.message
            for rec in caplog.records
        )
