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

def test_parse_event_missing_required_field():
    """Test parsing an event with a missing required field (e.g., event_type)."""
    timestamp_now = int(time.time())
    event_data = {
        "timestamp": timestamp_now,
        "payload": {"key": "value"}
    }
    with pytest.raises(EventError, match="Missing required event fields: event_type"):
        parse_event(event_data)

def test_parse_event_missing_multiple_required_fields():
    """Test parsing an event with multiple missing required fields."""
    event_data = {
        "payload": {"key": "value"}
    }
    # The order in the match string might vary, so check for individual field names
    with pytest.raises(EventError) as excinfo:
        parse_event(event_data)
    assert "Missing required event fields" in str(excinfo.value)
    assert "event_type" in str(excinfo.value)
    assert "timestamp" in str(excinfo.value)


def test_parse_event_invalid_type_for_event_type():
    """Test parsing an event with an invalid data type for event_type."""
    timestamp_now = int(time.time())
    event_data = {
        "event_type": 123, # Should be str
        "timestamp": timestamp_now,
        "payload": {"key": "value"}
    }
    with pytest.raises(EventError, match="Invalid type for 'event_type': expected str, got int"):
        parse_event(event_data)

def test_parse_event_invalid_type_for_timestamp():
    """Test parsing an event with an invalid data type for timestamp."""
    event_data = {
        "event_type": "test_event",
        "timestamp": "not-an-int", # Should be int
        "payload": {"key": "value"}
    }
    with pytest.raises(EventError, match="Invalid type for 'timestamp': expected int, got str"):
        parse_event(event_data)

def test_parse_event_invalid_type_for_payload():
    """Test parsing an event with an invalid data type for payload."""
    timestamp_now = int(time.time())
    event_data = {
        "event_type": "test_event",
        "timestamp": timestamp_now,
        "payload": "not-a-dict" # Should be dict
    }
    with pytest.raises(EventError, match="Invalid type for 'payload': expected dict, got str"):
        parse_event(event_data)

def test_event_creation_default_id():
    """Test that Event dataclass generates a default UUID for event_id."""
    event = Event(event_type="test", timestamp=int(time.time()), payload={})
    assert event.event_id is not None
    assert isinstance(event.event_id, str)
    # A simple check for UUID-like structure (36 chars, with hyphens)
    assert len(event.event_id) == 36
    assert "-" in event.event_id
