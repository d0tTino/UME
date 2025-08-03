"""Event ingestion helpers used by API and gRPC layers."""

from __future__ import annotations

from typing import Iterable, Dict, Any, cast, TYPE_CHECKING

from google.protobuf.json_format import MessageToDict
from ume_client import events_pb2 as _events_pb2
from google.protobuf import struct_pb2
from ..event import Event, EventError, EventType, parse_event
from ..processing import apply_event_to_graph
from ..graph_adapter import IGraphAdapter
from ..async_graph_adapter import IAsyncGraphAdapter, ingest_event_async
from ..classification import classify_event
from ..anomaly_detection import AnomalyDetector

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


def validate_event(data: Dict[str, Any]) -> Event:
    """Parse ``data`` into an :class:`~ume.event.Event`."""
    return parse_event(data)


def apply_event(event: Event, graph: IGraphAdapter) -> None:
    """Apply ``event`` to ``graph`` using :func:`~ume.processing.apply_event_to_graph`."""
    apply_event_to_graph(event, graph)


def ingest_event(data: Dict[str, Any], graph: IGraphAdapter) -> None:
    """Validate ``data``, classify it, and apply the resulting event to ``graph``."""
    event = validate_event(data)

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

    apply_event(event, graph)

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
        )


def ingest_events_batch(events: Iterable[Dict[str, Any]], graph: IGraphAdapter) -> None:
    """Sequentially ingest multiple events into ``graph``."""
    for data in events:
        ingest_event(data, graph)


def dict_to_envelope(data: Dict[str, Any]) -> Any:
    """Convert a raw event dictionary to :class:`~ume_client.events_pb2.EventEnvelope`."""
    evt = validate_event(data)
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
    if evt.event_type == EventType.CREATE_NODE.value:
        return events_pb2.EventEnvelope(create_node=events_pb2.CreateNode(meta=meta))
    if evt.event_type == EventType.UPDATE_NODE_ATTRIBUTES.value:
        return events_pb2.EventEnvelope(
            update_node_attributes=events_pb2.UpdateNodeAttributes(meta=meta)
        )
    if evt.event_type == EventType.CREATE_EDGE.value:
        return events_pb2.EventEnvelope(create_edge=events_pb2.CreateEdge(meta=meta))
    if evt.event_type == EventType.DELETE_EDGE.value:
        return events_pb2.EventEnvelope(delete_edge=events_pb2.DeleteEdge(meta=meta))
    raise ValueError(evt.event_type)


def envelope_to_event_dict(envelope: Any) -> Dict[str, Any]:
    """Convert an :class:`~ume_client.events_pb2.EventEnvelope` into a raw event dictionary."""
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

    return {
        "eventId": meta.event_id,
        "eventType": meta.event_type,
        "timestamp": meta.timestamp,
        "payload": MessageToDict(meta.payload),
        "sourceService": meta.source or None,
        "node_id": meta.node_id or None,
        "target_node_id": meta.target_node_id or None,
        "label": meta.label or None,
    }


def ingest_envelope(envelope: Any, graph: IGraphAdapter) -> None:
    """Ingest an :class:`EventEnvelope` into ``graph``."""
    ingest_event(envelope_to_event_dict(envelope), graph)


async def ingest_envelope_async(
    envelope: Any, graph: IAsyncGraphAdapter
) -> None:
    """Asynchronously ingest an :class:`EventEnvelope` into ``graph``."""
    await ingest_event_async(envelope_to_event_dict(envelope), graph)
