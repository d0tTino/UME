# src/ume/event.py
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Enumeration of built-in event types."""

    CREATE_NODE = "CREATE_NODE"
    UPDATE_NODE_ATTRIBUTES = "UPDATE_NODE_ATTRIBUTES"
    CREATE_EDGE = "CREATE_EDGE"
    DELETE_EDGE = "DELETE_EDGE"
    CREATE_ONTOLOGY_RELATION = "CREATE_ONTOLOGY_RELATION"


@dataclass(frozen=True)
class Event:
    """
    Represents a generic event within the UME system.

    Attributes:
        event_type (str): The type or category of the event (e.g., "user_interaction", "system_alert",
                          "CREATE_NODE", "CREATE_EDGE").
        timestamp (int | str): When the event occurred. Can be a Unix timestamp
            (seconds since epoch) or an ISO 8601 formatted string.
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
        correlation_id (Optional[str]): Optional ID to correlate related events.
        subject_entity (Optional[Dict[str, str]]): Entity this event refers to as an object
            with ``id`` and ``type`` keys.
        source_service (Optional[str]): Name of the service emitting the event.
    """

    event_type: str
    timestamp: int | str
    payload: Dict[str, Any]  # Main content, e.g., attributes for a node
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: Optional[str] = None
    node_id: Optional[str] = None  # Source node for edges, or target for node ops
    target_node_id: Optional[str] = None  # Target node for edges
    label: Optional[str] = None  # Label for edges
    correlation_id: Optional[str] = None
    subject_entity: Optional[Dict[str, str]] = None
    source_service: Optional[str] = None


class EventError(ValueError):
    """Custom exception for event parsing or validation errors."""

    pass


def parse_event(data: Dict[str, Any]) -> Event:
    """
    Parses a dictionary into an Event object, with validation based on event_type.

    Args:
        data (Dict[str, Any]): A dictionary potentially representing an event.
              Common expected keys: "eventType", "timestamp" (ISO 8601
              formatted string).
              Type-specific keys:
                - For "CREATE_NODE", "UPDATE_NODE_ATTRIBUTES": "node_id" (str), "payload" (dict).
                - For "CREATE_EDGE", "DELETE_EDGE": "node_id" (source, str),
                  "target_node_id" (str), "label" (str).
              Optional common keys: "eventId" (str), "sourceService" (str),
                "correlationId" (str), "subjectEntity" (object with ``id`` and ``type``).
              "payload" (dict) is optional for edge events, defaulting to {}.

    Returns:
        Event: An Event instance.

    Raises:
        EventError: If required fields are missing or have incorrect types for the given event_type.
    """
    logger.debug("Parsing event data: %s", data)

    # Basic presence and type checks for common fields
    if "eventType" in data:
        event_type = data["eventType"]
    elif "event_type" in data:
        event_type = data["event_type"]
    else:
        logger.error("Missing required event field: eventType")
        raise EventError("Missing required event field: eventType")
    if not isinstance(event_type, str):
        msg = f"Invalid type for 'eventType': expected str, got {type(event_type).__name__}"

        logger.error(msg)
        raise EventError(msg)
    # Map to the known EventType enum when possible but allow arbitrary strings
    event_type_enum: EventType | str
    try:
        event_type_enum = EventType(event_type)
        event_type_str = event_type_enum.value
    except ValueError:
        event_type_enum = event_type
        event_type_str = event_type

    if "timestamp" not in data:
        logger.error("Missing required event field: timestamp")
        raise EventError("Missing required event field: timestamp")
    timestamp_raw = data["timestamp"]
    if not isinstance(timestamp_raw, str):
        msg = (
            "Invalid type for 'timestamp': expected ISO 8601 string, "
            f"got {type(timestamp_raw).__name__}"
        )
        logger.error(msg)
        raise EventError(msg)
    try:
        dt = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
    except ValueError:
        msg = "Invalid timestamp format"
        logger.error(msg)
        raise EventError(msg)
    timestamp_int = int(dt.timestamp())

    # Validate optional event_id type
    event_id_val = data.get("eventId")

    # Get potential values, to be validated by type-specific logic or used if optional
    node_id_val = data.get("node_id")
    target_node_id_val = data.get("target_node_id")
    label_val = data.get("label")
    correlation_id_val = data.get("correlationId")
    subject_entity_val = data.get("subjectEntity")
    source_service_val = data.get("sourceService")
    # Default payload to {} if not present; specific event types might require it later
    payload_val = data.get("payload", {})

    if event_id_val is not None and not isinstance(event_id_val, str):
        msg = (
            f"Invalid type for 'eventId': expected str, got {type(event_id_val).__name__}"
        )
        logger.error(msg)
        raise EventError(msg)

    if correlation_id_val is not None and not isinstance(correlation_id_val, str):
        msg = (
            f"Invalid type for 'correlationId': expected str, got {type(correlation_id_val).__name__}"
        )
        logger.error(msg)
        raise EventError(msg)

    if subject_entity_val is not None:
        if not isinstance(subject_entity_val, dict):
            msg = (
                f"Invalid type for 'subjectEntity': expected object, got {type(subject_entity_val).__name__}"
            )
            logger.error(msg)
            raise EventError(msg)
        if not {"id", "type"} <= subject_entity_val.keys():
            msg = "subjectEntity must contain 'id' and 'type'"
            logger.error(msg)
            raise EventError(msg)
        if not isinstance(subject_entity_val.get("id"), str) or not isinstance(
            subject_entity_val.get("type"), str
        ):
            msg = "subjectEntity 'id' and 'type' must be strings"
            logger.error(msg)
            raise EventError(msg)

    if source_service_val is not None and not isinstance(source_service_val, str):
        msg = (
            f"Invalid type for 'sourceService': expected str, got {type(source_service_val).__name__}"
        )
        logger.error(msg)
        raise EventError(msg)

    if event_type in [
        EventType.CREATE_NODE,
        EventType.UPDATE_NODE_ATTRIBUTES,
    ]:
        if "node_id" not in data:  # Must be present in data
            msg = f"Missing required field 'node_id' for {event_type_str} event."
            logger.error(msg)
            raise EventError(msg)
        if not isinstance(node_id_val, str):
            msg = f"Invalid type for 'node_id' in {event_type_str} event: expected str, got {type(node_id_val).__name__}"
            logger.error(msg)
            raise EventError(msg)

        if "payload" not in data:  # Must be present in data for these types
            msg = f"Missing required field 'payload' for {event_type_str} event."
            logger.error(msg)
            raise EventError(msg)
        # Ensure payload_val (which could be the default {} if "payload" key was missing,
        # or the actual value if present) is a dict for these event types.
        if not isinstance(payload_val, dict):
            msg = f"Invalid type for 'payload' in {event_type_str} event: expected dict, got {type(payload_val).__name__}"
            logger.error(msg)
            raise EventError(msg)

    elif event_type in [
        EventType.CREATE_EDGE,
        EventType.DELETE_EDGE,
        EventType.CREATE_ONTOLOGY_RELATION,
    ]:
        required_fields_for_edge = {"node_id", "target_node_id", "label"}
        missing_fields = required_fields_for_edge - data.keys()
        if missing_fields:
            msg = f"Missing required fields for {event_type_str} event: {', '.join(sorted(list(missing_fields)))}"
            logger.error(msg)
            raise EventError(msg)

        # Validate types for these required fields
        for field_name, field_val_check in [
            ("node_id", node_id_val),
            ("target_node_id", target_node_id_val),
            ("label", label_val),
        ]:
            if not isinstance(
                field_val_check, str
            ):  # Already checked for presence by missing_fields logic
                msg = f"Invalid type for '{field_name}' in {event_type_str} event: expected str, got {type(field_val_check).__name__}"
                logger.error(msg)
                raise EventError(msg)

        # For edge events, payload_val will use its default {} if "payload" was not in data.
        # If "payload" was in data, we still need to ensure it's a dict.
        if "payload" in data and not isinstance(payload_val, dict):
            msg = f"Invalid type for 'payload' in {event_type_str} event (if provided): expected dict, got {type(payload_val).__name__}"
            logger.error(msg)
            raise EventError(msg)

    else:
        # Unknown event types: validate optional fields if provided
        if "payload" in data and not isinstance(payload_val, dict):
            msg = (
                f"Invalid type for 'payload': expected dict, got {type(payload_val).__name__}"
            )
            logger.error(msg)
            raise EventError(msg)
        for optional_name, optional_value in [
            ("node_id", node_id_val),
            ("target_node_id", target_node_id_val),
            ("label", label_val),
        ]:
            if optional_value is not None and not isinstance(optional_value, str):
                msg = (
                    f"Invalid type for '{optional_name}': expected str, got {type(optional_value).__name__}"
                )
                logger.error(msg)
                raise EventError(msg)

    return Event(
        event_id=event_id_val if event_id_val is not None else str(uuid.uuid4()),
        event_type=event_type,
        timestamp=timestamp_int,
        payload=payload_val,  # Use payload_val which is defaulted to {} or the actual value
        source=data.get("sourceService"),
        node_id=node_id_val,
        target_node_id=target_node_id_val,
        label=label_val,
        correlation_id=correlation_id_val,
        subject_entity=subject_entity_val,
        source_service=source_service_val,
    )
