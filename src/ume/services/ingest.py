"""Event ingestion helpers used by API and gRPC layers."""

from __future__ import annotations

from typing import Iterable, Dict, Any, cast, TYPE_CHECKING

from google.protobuf.json_format import MessageToDict
from ume_client import events_pb2 as _events_pb2
from google.protobuf import struct_pb2
from ..event import Event, EventError, EventType
from ..events.ingress import ingest_transport_payload
from ..events.versioning import resolve_schema_version
from ..processing import DEFAULT_VERSION, apply_event_to_graph
from ..graph_adapter import IGraphAdapter
from ..async_graph_adapter import IAsyncGraphAdapter, ingest_event_async
from ..anomaly_detection import AnomalyDetector
from ..schema_manager import DEFAULT_SCHEMA_MANAGER
from ..pipeline.core import EventPipelineOrchestrator
from .mutate import (
    MutationError,
    build_graph_projector,
    raise_for_rejected_outcome,
    run_mutation,
)

if TYPE_CHECKING:  # pragma: no cover - typing import for mypy
    from ume_client import events_pb2 as events_pb2_type
else:
    events_pb2_type = cast(Any, None)

events_pb2 = cast(Any, _events_pb2)

_anomaly_detector = AnomalyDetector()
_orchestrator = EventPipelineOrchestrator()

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
    """Canonicalize and parse incoming transport data into :class:`~ume.event.Event`."""
    canonical, event = ingest_transport_payload(data)
    result = run_mutation(data, source="service_validate", orchestrator=_orchestrator)
    try:
        raise_for_rejected_outcome(result)
    except MutationError as exc:
        raise EventError(str(exc)) from exc
    return result.event or event


def apply_event(
    event: Event, graph: IGraphAdapter, *, schema_version: str | None = None
) -> None:
    """Apply ``event`` to ``graph`` using :func:`~ume.processing.apply_event_to_graph`."""

    if schema_version is None:
        apply_event_to_graph(event, graph, schema_version=event.schema_version)
    else:
        apply_event_to_graph(event, graph, schema_version=schema_version)


def _fallback_schema_version() -> str:
    try:
        return DEFAULT_SCHEMA_MANAGER.get_schema().version
    except Exception:  # pragma: no cover - schema resources missing
        return ""


def _build_graph_projector(
    graph: IGraphAdapter,
    *,
    schema_version: str | None = None,
) -> Any:
    base_projector = build_graph_projector(graph, schema_version=schema_version)

    def _project(context: Any) -> dict[str, Any]:
        details = base_projector(context)
        event = context.effective_event
        if event is None:
            raise EventError("missing_canonical_or_event")
        effective_version = str(details.get("schema_version") or schema_version or DEFAULT_VERSION)
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
        return {**details, "schema_version": effective_version}

    return _project


def ingest_event(
    data: Dict[str, Any], graph: IGraphAdapter, *, schema_version: str | None = None
) -> None:
    """Validate ``data``, classify it, and apply the resulting event to ``graph``."""
    result = run_mutation(
        data,
        source="service_ingest",
        projector=_build_graph_projector(graph, schema_version=schema_version),
        orchestrator=_orchestrator,
    )
    try:
        raise_for_rejected_outcome(result)
    except MutationError as exc:
        raise EventError(str(exc)) from exc


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
    canonical, evt = ingest_transport_payload(data, adapter="grpc")
    schema_version = resolve_schema_version(
        canonical,
        fallback_version=_fallback_schema_version(),
        default_version=DEFAULT_VERSION,
    )
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
    envelope_kwargs = {"schema_version": schema_version}
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
    event_dict = envelope_to_event_dict(envelope)
    result = run_mutation(
        event_dict,
        source="service_ingest",
        adapter="grpc",
        projector=_build_graph_projector(graph, schema_version=schema_version),
        orchestrator=_orchestrator,
    )
    try:
        raise_for_rejected_outcome(result)
    except MutationError as exc:
        raise EventError(str(exc)) from exc


async def ingest_envelope_async(
    envelope: Any,
    graph: IAsyncGraphAdapter,
    *,
    schema_version: str | None = None,
) -> None:
    """Asynchronously ingest an :class:`EventEnvelope` into ``graph``."""
    event_dict = envelope_to_event_dict(envelope)
    await ingest_event_async(
        event_dict,
        graph,
        schema_version=schema_version,
    )
