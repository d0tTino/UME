"""Event ingestion helpers used by API and gRPC layers."""

from __future__ import annotations

from typing import Iterable, Dict, Any, cast, TYPE_CHECKING

from google.protobuf.json_format import MessageToDict
from ume_client import events_pb2 as _events_pb2
from google.protobuf import struct_pb2
from ..event import Event, EventError, EventType, parse_event
from ..processing import DEFAULT_VERSION, apply_event_to_graph
from ..graph_adapter import IGraphAdapter
from ..async_graph_adapter import IAsyncGraphAdapter, ingest_event_async
from ..classification import classify_event
from ..anomaly_detection import AnomalyDetector
from ..schema_manager import DEFAULT_SCHEMA_MANAGER

if TYPE_CHECKING:  # pragma: no cover - typing import for mypy
    from ume_client import events_pb2 as events_pb2_type
else:
    events_pb2_type = cast(Any, None)

events_pb2 = cast(Any, _events_pb2)

_anomaly_detector = AnomalyDetector()

__all__ = [
    "validate_event",
    "apply_event",
    "ingest_event",
    "ingest_events_batch",
    "envelope_to_event_dict",
    "ingest_envelope",
    "ingest_envelope_async",
    "dict_to_envelope",
]


def _unwrap_envelope(data: Dict[str, Any]) -> tuple[Dict[str, Any], str | None]:
    """Return the canonical event dictionary and optional schema version."""

    if "event" in data and isinstance(data["event"], dict):
        return cast(Dict[str, Any], data["event"]), cast(
            str | None, data.get("schema_version")
        )
    return data, cast(str | None, data.get("schema_version"))


def validate_event(data: Dict[str, Any]) -> Event:
    """Parse ``data`` into an :class:`~ume.event.Event`."""
    return parse_event(data)


def apply_event(
    event: Event, graph: IGraphAdapter, *, schema_version: str | None = None
) -> None:
    """Apply ``event`` to ``graph`` using :func:`~ume.processing.apply_event_to_graph`."""

    if schema_version is None:
        apply_event_to_graph(event, graph)
    else:
        apply_event_to_graph(event, graph, schema_version=schema_version)


def _fallback_schema_version() -> str:
    try:
        return DEFAULT_SCHEMA_MANAGER.get_schema().version
    except Exception:  # pragma: no cover - schema resources missing
        return ""


def _normalize_schema_version(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return None


def ingest_event(
    data: Dict[str, Any], graph: IGraphAdapter, *, schema_version: str | None = None
) -> None:
    """Validate ``data``, classify it, and apply the resulting event to ``graph``."""
    event_data, envelope_version = _unwrap_envelope(data)
    explicit_version = _normalize_schema_version(schema_version)
    normalized_envelope_version = _normalize_schema_version(envelope_version)
    normalized_payload_version = _normalize_schema_version(
        event_data.get("schema_version")
    )
    detected_version = normalized_envelope_version or normalized_payload_version
    effective_version = (
        explicit_version
        or detected_version
        or _normalize_schema_version(_fallback_schema_version())
        or DEFAULT_VERSION
    )

    event = validate_event(event_data)

    tag_results = classify_event(event)
    event.payload["classification"] = [
        {
            "tag": r.tag,
            "confidence": r.confidence,
            "domain": r.domain,
            "subdomain": r.subdomain,
            "sensitivity": r.sensitivity,
        }
        for r in tag_results
    ]
    if tag_results:
        attributes = event.payload.setdefault("attributes", {})
        attributes["tags"] = [r.tag for r in tag_results]
        attributes["tag_confidence"] = [r.confidence for r in tag_results]
        for r in tag_results:
            if r.domain and "domain" not in attributes:
                attributes["domain"] = r.domain
            if r.subdomain and "subdomain" not in attributes:
                attributes["subdomain"] = r.subdomain
            if r.sensitivity and "sensitivity" not in attributes:
                attributes["sensitivity"] = r.sensitivity

    apply_event(event, graph, schema_version=effective_version)

    anomaly_event = _anomaly_detector.process_event(event)
    if anomaly_event is not None:
        ingest_event(
            {
                "eventType": anomaly_event.event_type,
                "timestamp": anomaly_event.timestamp,
                "payload": anomaly_event.payload,
                "sourceService": anomaly_event.source,
            },
            graph,
            schema_version=effective_version,
        )


def ingest_events_batch(
    events: Iterable[Dict[str, Any]],
    graph: IGraphAdapter,
    *,
    schema_version: str | None = None,
) -> None:
    """Sequentially ingest multiple events into ``graph``."""
    for data in events:
        ingest_event(data, graph, schema_version=schema_version)


def dict_to_envelope(data: Dict[str, Any]) -> Any:
    """Convert a raw event dictionary to :class:`~ume_client.events_pb2.EventEnvelope`."""
    evt = validate_event(data)
    schema_version = _normalize_schema_version(data.get("schema_version"))
    if not schema_version:
        schema_version = _fallback_schema_version()
    struct_payload = struct_pb2.Struct()
    struct_payload.update(evt.payload)
    meta = events_pb2.BaseEvent(
        event_id=evt.event_id,
        event_type=evt.event_type,
        timestamp=evt.timestamp,
        source=evt.source or "",
        node_id=evt.node_id or "",
        target_node_id=evt.target_node_id or "",
        label=evt.label or "",
        payload=struct_payload,
    )
    envelope_kwargs = {"schema_version": schema_version or DEFAULT_VERSION}
    envelope = events_pb2.EventEnvelope(**envelope_kwargs)
    if evt.event_type == EventType.CREATE_NODE.value:
        return events_pb2.EventEnvelope(
            schema_version=schema_version,
            create_node=events_pb2.CreateNode(meta=meta),
        )
    if evt.event_type == EventType.UPDATE_NODE_ATTRIBUTES.value:
        return events_pb2.EventEnvelope(
            schema_version=schema_version,
            update_node_attributes=events_pb2.UpdateNodeAttributes(meta=meta),
        )
        return envelope
    if evt.event_type == EventType.CREATE_EDGE.value:
        return events_pb2.EventEnvelope(
            schema_version=schema_version,
            create_edge=events_pb2.CreateEdge(meta=meta),
        )
    if evt.event_type == EventType.DELETE_EDGE.value:
        return events_pb2.EventEnvelope(
            schema_version=schema_version,
            delete_edge=events_pb2.DeleteEdge(meta=meta),
        )
    raise ValueError(evt.event_type)


def envelope_to_event_dict(envelope: Any) -> Dict[str, Any]:
    """Convert an :class:`~ume_client.events_pb2.EventEnvelope` into a raw event dictionary."""
    schema_version = envelope.schema_version or _fallback_schema_version()
    if envelope.HasField("create_node"):
        meta = envelope.create_node.meta
    elif envelope.HasField("update_node_attributes"):
        meta = envelope.update_node_attributes.meta
    elif envelope.HasField("create_edge"):
        meta = envelope.create_edge.meta
    elif envelope.HasField("delete_edge"):
        meta = envelope.delete_edge.meta
    else:
        raise EventError("Envelope missing payload")

    event_dict = {
        "eventId": meta.event_id,
        "eventType": meta.event_type,
        "timestamp": meta.timestamp,
        "payload": MessageToDict(meta.payload),
        "sourceService": meta.source or None,
        "node_id": meta.node_id or None,
        "target_node_id": meta.target_node_id or None,
        "label": meta.label or None,
    }
    if schema_version:
        event_dict["schema_version"] = schema_version
    return event_dict


def ingest_envelope(
    envelope: Any, graph: IGraphAdapter, *, schema_version: str | None = None
) -> None:
    """Ingest an :class:`EventEnvelope` into ``graph``."""
    ingest_event(
        envelope_to_event_dict(envelope),
        graph,
        schema_version=schema_version,
    )


async def ingest_envelope_async(
    envelope: Any,
    graph: IAsyncGraphAdapter,
    *,
    schema_version: str | None = None,
) -> None:
    """Asynchronously ingest an :class:`EventEnvelope` into ``graph``."""
    await ingest_event_async(
        envelope_to_event_dict(envelope),
        graph,
        schema_version=schema_version,
    )
