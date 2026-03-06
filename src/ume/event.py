# src/ume/event.py
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Mapping
import logging

from .events.contract import canonical_timestamp_to_int
from .events.types import EventType
from .events.versioning import normalize_schema_version

logger = logging.getLogger(__name__)

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
        schema_version (Optional[str]): Event schema version used to resolve handler/schema behavior.
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
    producer_id: Optional[str] = None
    tenant: Optional[str] = None
    producer_signature: Optional[str] = None
    schema_version: Optional[str] = None


class EventError(ValueError):
    """Custom exception for event parsing or validation errors."""

    pass


def parse_event(data: Dict[str, Any]) -> Event:
    """Parse a canonicalized event dictionary into :class:`Event`."""
    logger.debug("Parsing canonical event data: %s", data)

    if not {"metadata", "graph", "payload"} <= data.keys():
        raise EventError(
            "parse_event expects canonicalized data with 'metadata', 'graph', and 'payload'"
        )

    metadata = data.get("metadata")
    graph = data.get("graph")
    payload_val = data.get("payload", {})
    if not isinstance(metadata, Mapping):
        raise EventError("Invalid canonical metadata")
    if not isinstance(graph, Mapping):
        raise EventError("Invalid canonical graph")
    if not isinstance(payload_val, dict):
        raise EventError(
            f"Invalid type for 'payload': expected dict, got {type(payload_val).__name__}"
        )

    event_type = metadata.get("event_type")
    if not isinstance(event_type, str):
        raise EventError("Missing required event field: event_type")

    timestamp_raw = metadata.get("timestamp")
    if timestamp_raw is None:
        raise EventError("Missing required event field: timestamp")
    try:
        timestamp_int = canonical_timestamp_to_int(timestamp_raw)
    except ValueError as exc:
        raise EventError("Invalid timestamp format") from exc

    event_id_val = metadata.get("event_id")
    schema_version_raw = metadata.get("schema_version")
    schema_version_val = normalize_schema_version(schema_version_raw)
    correlation_ids = metadata.get("correlation_ids")
    correlation_id_val = None
    if isinstance(correlation_ids, Mapping):
        correlation_id_val = correlation_ids.get("correlation_id")

    subject_entity_val = metadata.get("subject_entity")
    source_service_val = metadata.get("source")
    producer_id_val = metadata.get("producer_id")
    tenant_val = metadata.get("tenant")
    producer_signature_val = metadata.get("producer_signature")

    node_id_val = graph.get("node_id")
    target_node_id_val = graph.get("target_node_id")
    label_val = graph.get("label")

    if event_id_val is not None and not isinstance(event_id_val, str):
        raise EventError(
            f"Invalid type for 'event_id': expected str, got {type(event_id_val).__name__}"
        )
    if schema_version_raw is not None and schema_version_val is None:
        raise EventError(
            f"Invalid type for 'schema_version': expected non-empty str, got {type(schema_version_raw).__name__}"
        )
    if correlation_id_val is not None and not isinstance(correlation_id_val, str):
        raise EventError(
            f"Invalid type for 'correlation_id': expected str, got {type(correlation_id_val).__name__}"
        )
    if source_service_val is not None and not isinstance(source_service_val, str):
        raise EventError(
            f"Invalid type for 'source': expected str, got {type(source_service_val).__name__}"
        )
    if producer_id_val is not None and not isinstance(producer_id_val, str):
        raise EventError(
            f"Invalid type for 'producer_id': expected str, got {type(producer_id_val).__name__}"
        )
    if tenant_val is not None and not isinstance(tenant_val, str):
        raise EventError(
            f"Invalid type for 'tenant': expected str, got {type(tenant_val).__name__}"
        )
    if producer_signature_val is not None and not isinstance(producer_signature_val, str):
        raise EventError(
            f"Invalid type for 'producer_signature': expected str, got {type(producer_signature_val).__name__}"
        )
    if subject_entity_val is not None:
        if not isinstance(subject_entity_val, dict):
            raise EventError(
                f"Invalid type for 'subject_entity': expected object, got {type(subject_entity_val).__name__}"
            )
        if not {"id", "type"} <= subject_entity_val.keys():
            raise EventError("subject_entity must contain 'id' and 'type'")

    if event_type in [
        EventType.CREATE_NODE,
        EventType.UPDATE_NODE_ATTRIBUTES,
        EventType.RESEARCH_JOB_STARTED,
        EventType.DOCUMENT_ARCHIVED,
        EventType.REDACT_NODE,
    ]:
        payload_node_id = payload_val.get("node_id")
        if node_id_val is None and payload_node_id is not None:
            node_id_val = payload_node_id
        if node_id_val is None:
            raise EventError(f"Missing required field 'node_id' for {event_type} event.")
        if payload_node_id is not None and payload_node_id != node_id_val:
            raise EventError(
                f"Conflicting node_id values for {event_type} event: 'node_id' and 'payload.node_id' must match"
            )
        if event_type in [EventType.UPDATE_NODE_ATTRIBUTES, EventType.DOCUMENT_ARCHIVED]:
            if "attributes" not in payload_val or not isinstance(payload_val["attributes"], dict):
                raise EventError(
                    f"Missing required field 'payload.attributes' for {event_type} event."
                )

    elif event_type in [
        EventType.CREATE_EDGE,
        EventType.DELETE_EDGE,
        EventType.REDACT_EDGE,
        EventType.CREATE_ONTOLOGY_RELATION,
        EventType.DATA_SOURCE_QUERIED,
        EventType.ENTITY_DISCOVERED,
    ]:
        for field_name, field_val_check in [
            ("node_id", node_id_val),
            ("target_node_id", target_node_id_val),
            ("label", label_val),
        ]:
            if not isinstance(field_val_check, str):
                raise EventError(
                    f"Invalid type for '{field_name}' in {event_type} event: expected str, got {type(field_val_check).__name__}"
                )

    return Event(
        event_id=event_id_val if event_id_val is not None else str(uuid.uuid4()),
        event_type=event_type,
        timestamp=timestamp_int,
        payload=payload_val,
        source=source_service_val,
        node_id=node_id_val,
        target_node_id=target_node_id_val,
        label=label_val,
        correlation_id=correlation_id_val,
        subject_entity=subject_entity_val,
        source_service=source_service_val,
        producer_id=producer_id_val,
        tenant=tenant_val,
        producer_signature=producer_signature_val,
        schema_version=schema_version_val,
    )
