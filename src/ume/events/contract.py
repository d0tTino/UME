from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Mapping


"""Event contract transformations.

Authoritative ingress contract (external): flat producer payload with camelCase
metadata keys and snake_case graph keys:

    eventId, eventType, timestamp, schemaVersion, sourceService,
    producerId, tenant, signature, correlationId, subjectEntity,
    node_id, target_node_id, label, payload

Authoritative internal contract (canonical):

    {
      "metadata": {...},
      "graph": {...},
      "payload": {...}
    }

Transform direction is strictly external -> canonical in this module.
Legacy/backward shape upgrades must happen in ``ume.events.legacy_transform``.
"""


_CAMEL_TO_SNAKE = {
    "eventId": "event_id",
    "eventType": "event_type",
    "schemaVersion": "schema_version",
    "correlationId": "correlation_id",
    "sourceService": "source",
    "subjectEntity": "subject_entity",
    "producerId": "producer_id",
    "nodeId": "node_id",
    "targetNodeId": "target_node_id",
}

_SNAKE_TO_CAMEL = {
    "event_id": "eventId",
    "event_type": "eventType",
    "schema_version": "schemaVersion",
    "correlation_id": "correlationId",
    "subject_entity": "subjectEntity",
    "source": "sourceService",
}


@dataclass(frozen=True)
class CanonicalMetadata:
    event_id: str | None
    event_type: str | None
    timestamp: int | str | None
    schema_version: str | None
    source: str | None
    producer_id: str | None
    tenant: str | None
    producer_signature: str | None
    correlation_id: str | None
    subject_entity: Dict[str, str] | None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "schema_version": self.schema_version,
            "source": self.source,
            "producer_id": self.producer_id,
            "tenant": self.tenant,
            "producer_signature": self.producer_signature,
            "correlation_ids": {"correlation_id": self.correlation_id},
            "subject_entity": self.subject_entity,
        }


@dataclass(frozen=True)
class CanonicalGraph:
    node_id: str | None
    target_node_id: str | None
    label: str | None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "target_node_id": self.target_node_id,
            "label": self.label,
        }


@dataclass(frozen=True)
class CanonicalEnvelope:
    """Canonical in-memory shape used by parsers and transport adapters."""

    metadata: CanonicalMetadata
    graph: CanonicalGraph
    payload: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.as_dict(),
            "graph": self.graph.as_dict(),
            "payload": self.payload if isinstance(self.payload, dict) else self.payload,
        }


def _envelope_from_data(data: Mapping[str, Any]) -> CanonicalEnvelope:
    metadata = CanonicalMetadata(
        event_id=data.get("event_id"),
        event_type=data.get("event_type"),
        timestamp=data.get("timestamp"),
        schema_version=data.get("schema_version"),
        source=data.get("source"),
        producer_id=data.get("producer_id"),
        tenant=data.get("tenant"),
        producer_signature=data.get("producer_signature"),
        correlation_id=data.get("correlation_id"),
        subject_entity=data.get("subject_entity"),
    )
    graph = CanonicalGraph(
        node_id=data.get("node_id"),
        target_node_id=data.get("target_node_id"),
        label=data.get("label"),
    )
    payload = data.get("payload", {})
    if not isinstance(payload, dict):
        payload = payload
    return CanonicalEnvelope(metadata=metadata, graph=graph, payload=payload)


def _to_snake_keys(data: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in data.items():
        normalized_key = _CAMEL_TO_SNAKE.get(key, key)
        if normalized_key == "event" and isinstance(value, Mapping):
            out[normalized_key] = _to_snake_keys(value)
        else:
            out[normalized_key] = value
    return out


def _to_external_contract(data: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate/normalize the single authoritative external producer contract."""

    if "event" in data:
        raise ValueError(
            "event envelope contract is not accepted; run ume.events.legacy_transform first"
        )
    if "event_type" in data or "event_id" in data or "schema_version" in data:
        raise ValueError(
            "snake_case ingest fields are not accepted; run ume.events.legacy_transform first"
        )

    external: Dict[str, Any] = {
        "eventId": data.get("eventId"),
        "eventType": data.get("eventType"),
        "timestamp": data.get("timestamp"),
        "payload": data.get("payload", {}),
        "sourceService": data.get("sourceService"),
        "producerId": data.get("producerId"),
        "tenant": data.get("tenant"),
        "signature": data.get("signature"),
        "schemaVersion": data.get("schemaVersion"),
        "node_id": data.get("node_id"),
        "target_node_id": data.get("target_node_id"),
        "label": data.get("label"),
        "correlationId": data.get("correlationId"),
        "subjectEntity": data.get("subjectEntity"),
    }
    return {k: v for k, v in external.items() if v is not None}


def canonicalize_event(data: Mapping[str, Any]) -> Dict[str, Any]:
    """Transform authoritative external ingest payload into canonical envelope."""

    external_data = _to_external_contract(data)
    snake_data = _to_snake_keys(external_data)

    resolved = {
        **snake_data,
        "source": snake_data.get("source_service") or snake_data.get("source"),
        "producer_id": snake_data.get("producer_id"),
        "tenant": snake_data.get("tenant"),
        "producer_signature": snake_data.get("producer_signature") or snake_data.get("signature"),
        "schema_version": snake_data.get("schema_version"),
    }
    return _envelope_from_data(resolved).as_dict()


def canonical_to_legacy_dict(canonical: Mapping[str, Any]) -> Dict[str, Any]:
    """Flatten canonical envelope to the historical event dictionary shape."""

    metadata = canonical.get("metadata", {})
    graph = canonical.get("graph", {})
    payload = canonical.get("payload", {})
    correlation_ids = metadata.get("correlation_ids", {}) if isinstance(metadata, Mapping) else {}

    event = {
        "eventId": metadata.get("event_id"),
        "eventType": metadata.get("event_type"),
        "timestamp": metadata.get("timestamp"),
        "payload": payload if isinstance(payload, dict) else payload,
        "sourceService": metadata.get("source"),
        "producerId": metadata.get("producer_id"),
        "tenant": metadata.get("tenant"),
        "signature": metadata.get("producer_signature"),
        "node_id": graph.get("node_id"),
        "target_node_id": graph.get("target_node_id"),
        "label": graph.get("label"),
        "correlationId": correlation_ids.get("correlation_id"),
        "subjectEntity": metadata.get("subject_entity"),
    }
    schema_version = metadata.get("schema_version")
    if isinstance(schema_version, str) and schema_version.strip():
        event["schema_version"] = schema_version
    return {k: v for k, v in event.items() if v is not None}


def canonical_to_camel_dict(canonical: Mapping[str, Any]) -> Dict[str, Any]:
    """Flatten canonical envelope to camelCase transport keys."""

    flat = canonical_to_legacy_dict(canonical)
    out: Dict[str, Any] = {}
    for key, value in flat.items():
        out[_SNAKE_TO_CAMEL.get(key, key)] = value
    return out


def canonical_timestamp_to_int(timestamp_raw: int | str) -> int:
    if isinstance(timestamp_raw, int):
        return timestamp_raw
    if isinstance(timestamp_raw, str):
        dt = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
        return int(dt.timestamp())
    raise ValueError("Invalid timestamp")
