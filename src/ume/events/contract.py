from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Mapping


_CAMEL_TO_SNAKE = {
    "eventId": "event_id",
    "eventType": "event_type",
    "schemaVersion": "schema_version",
    "correlationId": "correlation_id",
    "sourceService": "source",
    "subjectEntity": "subject_entity",
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
    correlation_id: str | None
    subject_entity: Dict[str, str] | None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "schema_version": self.schema_version,
            "source": self.source,
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
    """Normalize adapter output to the single external producer contract."""

    if "event" in data:
        raise ValueError("event envelope contract is not accepted; send flat event fields")

    normalized = _to_snake_keys(data)
    if "source" in normalized and "source_service" not in normalized:
        normalized["source_service"] = normalized["source"]

    external: Dict[str, Any] = {
        "eventId": normalized.get("event_id"),
        "eventType": normalized.get("event_type"),
        "timestamp": normalized.get("timestamp"),
        "payload": normalized.get("payload", {}),
        "sourceService": normalized.get("source_service"),
        "schemaVersion": normalized.get("schema_version"),
        "node_id": normalized.get("node_id"),
        "target_node_id": normalized.get("target_node_id"),
        "label": normalized.get("label"),
        "correlationId": normalized.get("correlation_id"),
        "subjectEntity": normalized.get("subject_entity"),
    }
    return {k: v for k, v in external.items() if v is not None}


def canonicalize_event(data: Mapping[str, Any]) -> Dict[str, Any]:
    """Normalize flat external producer event into the canonical envelope dict."""

    external_data = _to_external_contract(data)
    snake_data = _to_snake_keys(external_data)

    resolved = {
        **snake_data,
        "source": snake_data.get("source_service") or snake_data.get("source"),
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
