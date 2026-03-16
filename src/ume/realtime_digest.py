from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from .realtime_contracts import GraphDigestEvent


def event_payload_hash(payload: Dict[str, Any] | None) -> str:
    serialized = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def to_graph_digest(offset: int, event: Dict[str, Any]) -> GraphDigestEvent:
    return GraphDigestEvent(
        offset=offset,
        event_id=event.get("event_id") or event.get("eventId"),
        event_type=str(event.get("event_type") or event.get("eventType") or "UNKNOWN"),
        source_service=event.get("source") or event.get("sourceService"),
        schema_version=event.get("schema_version") or event.get("schemaVersion"),
        timestamp=event.get("timestamp"),
        node_id=event.get("node_id"),
        target_node_id=event.get("target_node_id") or event.get("targetNodeId"),
        label=event.get("label"),
        payload_hash=event_payload_hash(event.get("payload")),
    )

