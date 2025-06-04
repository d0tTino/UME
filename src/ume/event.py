# src/ume/event.py
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass(frozen=True)
class Event:
    """
    Represents a generic event within the UME system.

    Attributes:
        event_type (str): The type or category of the event (e.g., "user_interaction", "system_alert",
                          "CREATE_NODE", "CREATE_EDGE").
        timestamp (int): Unix timestamp (seconds since epoch) indicating when the event occurred or was generated.
        payload (Dict[str, Any]): A dictionary containing the actual data/details of the event.
                                  The structure of the payload can vary based on the event_type.
                                  For node-related events, this often contains node attributes.
                                  For edge-related events, this might be empty or contain edge attributes.
        event_id (str): A unique identifier for the event, typically a UUID. Defaults to a new UUID4.
        source (Optional[str]): An optional identifier for the source of the event
                                (e.g., "producer_demo", "external_api"). Defaults to None.
        node_id (Optional[str]): The identifier of the primary node associated with the event.
                                 For node creation/update, this is the target node.
                                 For edge creation, this is the source node. Defaults to None.
        target_node_id (Optional[str]): The identifier of the target node, used for edge-related events
                                          (e.g., CREATE_EDGE, DELETE_EDGE). Defaults to None.
        label (Optional[str]): A label describing an edge or a relationship, used for edge-related events.
                                 Defaults to None.
    """
    event_type: str
    timestamp: int
    payload: Dict[str, Any] # Main content, e.g., attributes for a node
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: Optional[str] = None
    node_id: Optional[str] = None  # Source node for edges, or target for node ops
    target_node_id: Optional[str] = None # Target node for edges
    label: Optional[str] = None # Label for edges

class EventError(ValueError):
    """Custom exception for event parsing or validation errors."""
    pass

def parse_event(data: Dict[str, Any]) -> Event:
    """
    Parses a dictionary into an Event object, with validation based on event_type.

    Args:
        data (Dict[str, Any]): A dictionary potentially representing an event.
              Common expected keys: "event_type", "timestamp".
              Type-specific keys:
                - For "CREATE_NODE", "UPDATE_NODE_ATTRIBUTES": "node_id" (str), "payload" (dict).
                - For "CREATE_EDGE", "DELETE_EDGE": "node_id" (source, str),
                  "target_node_id" (str), "label" (str).
              Optional common keys: "event_id" (str), "source" (str).
              "payload" (dict) is optional for edge events, defaulting to {}.

    Returns:
        Event: An Event instance.

    Raises:
        EventError: If required fields are missing or have incorrect types for the given event_type.
    """
    # Basic presence and type checks for common fields
    if "event_type" not in data:
        raise EventError("Missing required event field: event_type")
    event_type = data["event_type"]
    if not isinstance(event_type, str):
        raise EventError(f"Invalid type for 'event_type': expected str, got {type(event_type).__name__}")

    if "timestamp" not in data:
        raise EventError("Missing required event field: timestamp")
    timestamp = data["timestamp"]
    if not isinstance(timestamp, int):
        raise EventError(f"Invalid type for 'timestamp': expected int, got {type(timestamp).__name__}")

    # Get potential values, to be validated by type-specific logic or used if optional
    node_id_val = data.get("node_id")
    target_node_id_val = data.get("target_node_id")
    label_val = data.get("label")
    # Default payload to {} if not present; specific event types might require it later
    payload_val = data.get("payload", {})

    if event_type in ["CREATE_NODE", "UPDATE_NODE_ATTRIBUTES"]:
        if "node_id" not in data: # Must be present in data
            raise EventError(f"Missing required field 'node_id' for {event_type} event.")
        if not isinstance(node_id_val, str):
            raise EventError(f"Invalid type for 'node_id' in {event_type} event: expected str, got {type(node_id_val).__name__}")

        if "payload" not in data: # Must be present in data for these types
             raise EventError(f"Missing required field 'payload' for {event_type} event.")
        # Ensure payload_val (which could be the default {} if "payload" key was missing,
        # or the actual value if present) is a dict for these event types.
        if not isinstance(payload_val, dict):
            raise EventError(f"Invalid type for 'payload' in {event_type} event: expected dict, got {type(payload_val).__name__}")

    elif event_type in ["CREATE_EDGE", "DELETE_EDGE"]:
        required_fields_for_edge = {"node_id", "target_node_id", "label"}
        missing_fields = required_fields_for_edge - data.keys()
        if missing_fields:
            raise EventError(f"Missing required fields for {event_type} event: {', '.join(sorted(list(missing_fields)))}")

        # Validate types for these required fields
        for field_name, field_val_check in [("node_id", node_id_val), ("target_node_id", target_node_id_val), ("label", label_val)]:
            if not isinstance(field_val_check, str): # Already checked for presence by missing_fields logic
                raise EventError(f"Invalid type for '{field_name}' in {event_type} event: expected str, got {type(field_val_check).__name__}")

        # For edge events, payload_val will use its default {} if "payload" was not in data.
        # If "payload" was in data, we still need to ensure it's a dict.
        if "payload" in data and not isinstance(payload_val, dict):
             raise EventError(f"Invalid type for 'payload' in {event_type} event (if provided): expected dict, got {type(payload_val).__name__}")


    return Event(
        event_id=data.get("event_id", str(uuid.uuid4())),
        event_type=event_type,
        timestamp=timestamp,
        payload=payload_val, # Use payload_val which is defaulted to {} or the actual value
        source=data.get("source"),
        node_id=node_id_val,
        target_node_id=target_node_id_val,
        label=label_val
    )
