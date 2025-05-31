# src/ume/event.py
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass(frozen=True)
class Event:
    """
    Represents a generic event within the UME system.

    Attributes:
        event_type (str): The type or category of the event (e.g., "user_interaction", "system_alert").
        timestamp (int): Unix timestamp (seconds since epoch) indicating when the event occurred or was generated.
        payload (Dict[str, Any]): A dictionary containing the actual data/details of the event.
                                The structure of the payload can vary based on the event_type.
        event_id (str): A unique identifier for the event, typically a UUID. Defaults to a new UUID4.
        source (Optional[str]): An optional identifier for the source of the event (e.g., "producer_demo", "external_api").
    """
    event_type: str
    timestamp: int
    payload: Dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: Optional[str] = None

class EventError(ValueError):
    """Custom exception for event parsing or validation errors."""
    pass

def parse_event(data: Dict[str, Any]) -> Event:
    """
    Parses a dictionary into an Event object.

    Args:
        data: A dictionary potentially representing an event.
              Expected keys: "event_type", "timestamp", "payload".
              Optional keys: "event_id", "source".

    Returns:
        An Event instance.

    Raises:
        EventError: If required fields are missing or have incorrect types.
    """
    required_fields = {"event_type", "timestamp", "payload"}
    missing_fields = required_fields - data.keys()
    if missing_fields:
        raise EventError(f"Missing required event fields: {', '.join(sorted(list(missing_fields)))}")

    if not isinstance(data["event_type"], str):
        raise EventError(f"Invalid type for 'event_type': expected str, got {type(data['event_type']).__name__}")
    if not isinstance(data["timestamp"], int):
        raise EventError(f"Invalid type for 'timestamp': expected int, got {type(data['timestamp']).__name__}")
    if not isinstance(data["payload"], dict):
        raise EventError(f"Invalid type for 'payload': expected dict, got {type(data['payload']).__name__}")

    return Event(
        event_id=data.get("event_id", str(uuid.uuid4())), # Use provided or generate new
        event_type=data["event_type"],
        timestamp=data["timestamp"],
        payload=data["payload"],
        source=data.get("source")
    )
