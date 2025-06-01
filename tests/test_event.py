# tests/test_event.py
import pytest
import time
from ume import Event, parse_event, EventError # Assuming __init__.py exports these

def test_parse_event_valid():
    """Test parsing a valid event dictionary."""
    timestamp_now = int(time.time())
    event_data = {
        "event_id": "test-id-123",
        "event_type": "test_event",
        "timestamp": timestamp_now,
        "payload": {"key": "value", "num": 123},
        "source": "test_source"
    }
    event = parse_event(event_data)
    assert isinstance(event, Event)
    assert event.event_id == "test-id-123"
    assert event.event_type == "test_event"
    assert event.timestamp == timestamp_now
    assert event.payload == {"key": "value", "num": 123}
    assert event.source == "test_source"

def test_parse_event_minimal_valid():
    """Test parsing a minimal valid event dictionary (event_id and source generated)."""
    timestamp_now = int(time.time())
    event_data = {
        "event_type": "minimal_event",
        "timestamp": timestamp_now,
        "payload": {"data": "minimal_data"}
    }
    event = parse_event(event_data)
    assert isinstance(event, Event)
    assert event.event_type == "minimal_event"
    assert event.timestamp == timestamp_now
    assert event.payload == {"data": "minimal_data"}
    assert event.event_id is not None # Should be auto-generated
    assert isinstance(event.event_id, str)
    assert event.source is None # Should default to None

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
        ({}, "Missing required event fields"),

        # Case 2: Missing 'event_type'
        ({"timestamp": 123, "payload": {}}, "Missing required event fields: event_type"),

        # Case 3: Missing 'timestamp'
        ({"event_type": "test", "payload": {}}, "Missing required event fields: timestamp"),

        # Case 4: Missing 'payload'
        ({"event_type": "test", "timestamp": 123}, "Missing required event fields: payload"),

        # Case 5: Invalid type for 'event_type' (int instead of str)
        ({"event_type": 123, "timestamp": int(time.time()), "payload": {}}, "Invalid type for 'event_type'"),

        # Case 6: Invalid type for 'timestamp' (str instead of int)
        ({"event_type": "test", "timestamp": "not-an-int", "payload": {}}, "Invalid type for 'timestamp'"),

        # Case 7: Invalid type for 'payload' (str instead of dict)
        ({"event_type": "test", "timestamp": int(time.time()), "payload": "not-a-dict"}, "Invalid type for 'payload'"),
    ]
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
