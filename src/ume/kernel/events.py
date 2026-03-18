"""Kernel event model and parsing helpers."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Mapping, Optional

from ..events.contract import CanonicalPayload
from ..events.contract_registry import load_event_contracts

logger = logging.getLogger(__name__)


_EVENT_CONTRACTS = load_event_contracts()


class EventType(str, Enum):
    """Enumeration of built-in event types."""

    CREATE_NODE = "CREATE_NODE"
    UPDATE_NODE_ATTRIBUTES = "UPDATE_NODE_ATTRIBUTES"
    CREATE_EDGE = "CREATE_EDGE"
    DELETE_EDGE = "DELETE_EDGE"
    REDACT_NODE = "REDACT_NODE"
    REDACT_EDGE = "REDACT_EDGE"
    CREATE_ONTOLOGY_RELATION = "CREATE_ONTOLOGY_RELATION"
    RESEARCH_JOB_STARTED = "RESEARCH_JOB_STARTED"
    DATA_SOURCE_QUERIED = "DATA_SOURCE_QUERIED"
    ENTITY_DISCOVERED = "ENTITY_DISCOVERED"
    DOCUMENT_ARCHIVED = "DOCUMENT_ARCHIVED"
    ANOMALY_DETECTED = "ANOMALY_DETECTED"


@dataclass(frozen=True)
class Event:
    event_type: str
    timestamp: int | str
    payload: Dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: Optional[str] = None
    node_id: Optional[str] = None
    target_node_id: Optional[str] = None
    label: Optional[str] = None
    correlation_id: Optional[str] = None
    subject_entity: Optional[Dict[str, str]] = None
    source_service: Optional[str] = None
    producer_id: Optional[str] = None
    tenant: Optional[str] = None
    producer_signature: Optional[str] = None
    schema_version: Optional[str] = None


class EventError(ValueError):
    """Custom exception for event parsing or validation errors."""


def _raise_event_error(message: str) -> None:
    logger.error(message)
    raise EventError(message)


def _canonical_timestamp_to_int(timestamp_raw: int | str) -> int:
    if isinstance(timestamp_raw, int):
        return timestamp_raw
    if isinstance(timestamp_raw, str):
        dt = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
        return int(dt.timestamp())
    raise ValueError("Invalid timestamp")


def _normalize_schema_version(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return None


def parse_event(data: Dict[str, Any]) -> Event:
    logger.debug("Parsing canonical event data: %s", data)

    if not {"metadata", "graph", "payload"} <= data.keys():
        _raise_event_error(
            "parse_event expects canonicalized data with 'metadata', 'graph', and 'payload'; apply ume.events.legacy_transform before canonicalization for historical transport shapes"
        )

    metadata = data.get("metadata")
    graph = data.get("graph")
    payload_val = data.get("payload", {})
    if not isinstance(metadata, Mapping):
        _raise_event_error("Invalid canonical metadata")
    if not isinstance(graph, Mapping):
        _raise_event_error("Invalid canonical graph")

    event_type = metadata.get("event_type")
    if event_type is None:
        _raise_event_error("Missing required event field: eventType")
    if not isinstance(event_type, str):
        _raise_event_error(
            f"Invalid type for 'eventType': expected str, got {type(event_type).__name__}"
        )

    contract = _EVENT_CONTRACTS.get(event_type)

    if not isinstance(payload_val, dict):
        if contract is not None:
            if "payload" in contract.required_fields:
                _raise_event_error(f"Invalid type for 'payload' in {event_type} event: expected dict")
            _raise_event_error(
                f"Invalid type for 'payload' in {event_type} event (if provided): expected dict"
            )
        _raise_event_error(f"Invalid type for 'payload': expected dict, got {type(payload_val).__name__}")

    payload_present = not isinstance(payload_val, CanonicalPayload) or payload_val.payload_present

    timestamp_raw = metadata.get("timestamp")
    if timestamp_raw is None:
        _raise_event_error("Missing required event field: timestamp")
    try:
        timestamp_int = _canonical_timestamp_to_int(timestamp_raw)
    except ValueError as exc:
        _raise_event_error("Invalid timestamp format")
        raise AssertionError("unreachable") from exc

    event_id_val = metadata.get("event_id")
    schema_version_raw = metadata.get("schema_version")
    schema_version_val = _normalize_schema_version(schema_version_raw)
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
        _raise_event_error(
            f"Invalid type for 'eventId': expected str, got {type(event_id_val).__name__}"
        )
    if schema_version_raw is not None and schema_version_val is None:
        _raise_event_error(
            f"Invalid type for 'schema_version': expected non-empty str, got {type(schema_version_raw).__name__}"
        )
    if correlation_id_val is not None and not isinstance(correlation_id_val, str):
        _raise_event_error(
            f"Invalid type for 'correlationId': expected str, got {type(correlation_id_val).__name__}"
        )
    if source_service_val is not None and not isinstance(source_service_val, str):
        _raise_event_error(
            f"Invalid type for 'sourceService': expected str, got {type(source_service_val).__name__}"
        )
    if producer_id_val is not None and not isinstance(producer_id_val, str):
        _raise_event_error(
            f"Invalid type for 'producerId': expected str, got {type(producer_id_val).__name__}"
        )
    if tenant_val is not None and not isinstance(tenant_val, str):
        _raise_event_error(
            f"Invalid type for 'tenant': expected str, got {type(tenant_val).__name__}"
        )
    if producer_signature_val is not None and not isinstance(producer_signature_val, str):
        _raise_event_error(
            f"Invalid type for 'signature': expected str, got {type(producer_signature_val).__name__}"
        )
    if subject_entity_val is not None:
        if not isinstance(subject_entity_val, dict):
            _raise_event_error(
                f"Invalid type for 'subjectEntity': expected object, got {type(subject_entity_val).__name__}"
            )
        if not {"id", "type"} <= subject_entity_val.keys():
            _raise_event_error("subjectEntity must contain 'id' and 'type'")

    if contract is not None:
        if "payload" in contract.required_fields and not payload_present:
            _raise_event_error(f"Missing required field 'payload' for {event_type} event.")

        if contract.graph_required_fields == {"node_id"}:
            payload_node_id = payload_val.get("node_id")
            if node_id_val is None and payload_node_id is not None:
                node_id_val = payload_node_id
            if node_id_val is None:
                _raise_event_error(f"Missing required field 'node_id' for {event_type} event.")
            if payload_node_id is not None and payload_node_id != node_id_val:
                _raise_event_error(
                    f"Conflicting node_id values for {event_type} event: 'node_id' and 'payload.node_id' must match"
                )
        elif contract.graph_required_fields:
            missing_graph_fields = []
            for field_name, field_val_check in [
                ("node_id", node_id_val),
                ("target_node_id", target_node_id_val),
                ("label", label_val),
            ]:
                if field_name not in contract.graph_required_fields:
                    continue
                if field_val_check is None:
                    missing_graph_fields.append(field_name)
                elif not isinstance(field_val_check, str):
                    _raise_event_error(
                        f"Invalid type for '{field_name}' in {event_type} event: expected str, got {type(field_val_check).__name__}"
                    )
            if missing_graph_fields:
                _raise_event_error(
                    f"Missing required fields for {event_type} event: {', '.join(missing_graph_fields)}"
                )

        if "attributes" in contract.payload_required_fields:
            attributes = payload_val.get("attributes")
            if not isinstance(attributes, dict):
                _raise_event_error(
                    f"Missing required field 'payload.attributes' for {event_type} event."
                )

    return Event(
        event_id=event_id_val if event_id_val is not None else str(uuid.uuid4()),
        event_type=event_type,
        timestamp=timestamp_int,
        payload=dict(payload_val),
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


__all__ = ["Event", "EventError", "EventType", "parse_event"]
