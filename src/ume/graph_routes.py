from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import time
from typing import Any, AsyncGenerator, Dict, List
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Header, Query
try:  # pragma: no cover - optional dependency
    from fastapi_limiter.depends import RateLimiter
except Exception:  # pragma: no cover - provide stub for tests without limiter
    def RateLimiter(*_args: Any, **_kwargs: Any):  # type: ignore
        async def _noop(*__args: Any, **__kwargs: Any) -> None:
            return None

        return _noop
from pydantic import BaseModel, Field, AliasChoices, ConfigDict, model_validator
from pydantic_core import PydanticCustomError
from sse_starlette.sse import EventSourceResponse

from .analytics import shortest_path
from .config import settings
from .document_guru import reformat_document
from .reliability import filter_low_confidence
import inspect
from .graph_adapter import IGraphAdapter
from .async_graph_adapter import IAsyncGraphAdapter, ingest_event_async
from .permissions_adapter import PermissionsGraphAdapter
from .query import Neo4jQueryEngine, build_events_query
from .event import EventError
from .processing import ProcessingError
from .graph_schema import DEFAULT_SCHEMA
from .event_ledger import event_ledger
from .realtime_contracts import GraphDigestControlEvent, GraphDigestEvent
from .rbac_adapter import AccessDeniedError
from ume.services.ingest import ingest_event, ingest_events_batch

# import shared API dependencies
from . import api_deps as deps

router = APIRouter()

_ROUTE_SOURCE_SERVICE = "graph_routes"


def _command_metadata(perm_graph: PermissionsGraphAdapter) -> Dict[str, Any]:
    return {
        "requested_by": {
            "user_id": perm_graph.user_id,
            "group_id": perm_graph.group_id,
        },
        "route": "graph_routes",
    }


def _canonical_command_event(
    *,
    event_type: str,
    node_id: str | None = None,
    target_node_id: str | None = None,
    label: str | None = None,
    payload: Dict[str, Any] | None = None,
    metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    command_payload = dict(payload or {})
    if metadata:
        command_payload["metadata"] = metadata
    return {
        "eventType": event_type,
        "eventId": str(uuid4()),
        "timestamp": int(time.time()),
        "sourceService": _ROUTE_SOURCE_SERVICE,
        "node_id": node_id,
        "target_node_id": target_node_id,
        "label": label,
        "payload": command_payload,
    }


def _require_edge_permissions(
    perm_graph: PermissionsGraphAdapter,
    source: str,
    target: str,
    label: str,
) -> None:
    perm_graph._require_editor(source)
    if label not in {"OWNED_BY", "SHARED_WITH", "INVITES"}:
        perm_graph._require_editor(target)


async def _ingest_event_dispatch(event: Dict[str, Any], graph: IGraphAdapter) -> None:
    if isinstance(graph, IAsyncGraphAdapter) or inspect.iscoroutinefunction(
        getattr(graph, "add_node", None)
    ):
        await ingest_event_async(event, graph)  # type: ignore[arg-type]
    else:
        ingest_event(event, graph)


async def _ingest_events_batch_dispatch(events: List[Dict[str, Any]], graph: IGraphAdapter) -> None:
    if isinstance(graph, IAsyncGraphAdapter) or inspect.iscoroutinefunction(
        getattr(graph, "add_node", None)
    ):
        for event in events:
            await ingest_event_async(event, graph)  # type: ignore[arg-type]
    else:
        ingest_events_batch(events, graph)


async def _maybe_call(graph: IGraphAdapter, name: str, *args: Any) -> Any:
    func = getattr(graph, name)
    if inspect.iscoroutinefunction(func) or isinstance(graph, IAsyncGraphAdapter):
        result = await func(*args)
    else:
        result = func(*args)
    if inspect.isawaitable(result):
        result = await result
    return result


async def _ensure_viewable(
    node_id: str,
    perm_graph: PermissionsGraphAdapter,
    graph: IGraphAdapter,
    not_found_detail: str,
) -> Dict[str, Any]:
    """Return node attributes if visible or raise 403/404."""

    attrs = perm_graph.get_node(node_id)
    if attrs is not None:
        return attrs

    existing = await _maybe_call(graph, "get_node", node_id)
    if existing is not None:
        raise HTTPException(status_code=403, detail="Access denied")
    raise HTTPException(status_code=404, detail=not_found_detail)


class ShortestPathRequest(BaseModel):
    source: str
    target: str


class PathRequest(BaseModel):
    source: str
    target: str
    max_depth: int | None = None
    edge_label: str | None = None
    since_timestamp: int | None = None


class SubgraphRequest(BaseModel):
    start: str
    depth: int
    edge_label: str | None = None
    since_timestamp: int | None = None


class NodeCreateRequest(BaseModel):
    id: str
    attributes: Dict[str, Any] | None = None


class NodeUpdateRequest(BaseModel):
    attributes: Dict[str, Any]


class EdgeCreateRequest(BaseModel):
    source: str
    target: str
    label: str
    attrs: Dict[str, Any] | None = None

    @model_validator(mode="after")
    def _require_permission_level(self) -> "EdgeCreateRequest":
        if self.label in {"OWNED_BY", "SHARED_WITH"}:
            attrs = self.attrs or {}
            perm = attrs.get("permission_level")
            if not isinstance(perm, str) or not perm:
                raise PydanticCustomError(
                    "permission_level_missing",
                    "permission_level is required for OWNED_BY/SHARED_WITH edges",
                )
        return self


class RedactEdgeRequest(BaseModel):
    source: str
    target: str
    label: str


class TweetCreateRequest(BaseModel):
    text: str


class DocumentUploadRequest(BaseModel):
    content: str


class SnapshotPathRequest(BaseModel):
    path: str


class EventRequest(BaseModel):
    """Schema for a single event."""

    model_config = ConfigDict(populate_by_name=True)

    event_type: str = Field(validation_alias=AliasChoices("event_type", "eventType"))
    timestamp: int
    event_id: str | None = Field(default=None, validation_alias=AliasChoices("event_id", "eventId"))
    source: str | None = Field(default=None, validation_alias=AliasChoices("source", "sourceService"))
    node_id: str | None = None
    target_node_id: str | None = Field(default=None, validation_alias=AliasChoices("target_node_id", "targetNodeId"))
    label: str | None = None
    schema_version: str | None = Field(default=None, validation_alias=AliasChoices("schema_version", "schemaVersion"))
    payload: Dict[str, Any] | None = None

    def to_ingress_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "node_id": self.node_id,
            "target_node_id": self.target_node_id,
            "label": self.label,
            "schema_version": self.schema_version,
            "payload": self.payload,
        }
    

def _event_payload_hash(payload: Dict[str, Any] | None) -> str:
    serialized = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _to_graph_digest(offset: int, event: Dict[str, Any]) -> GraphDigestEvent:
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
        payload_hash=_event_payload_hash(event.get("payload")),
    )


@router.get("/query")
def run_cypher(
    cypher: str,
    _: str = Depends(deps.get_current_role),
    engine: Neo4jQueryEngine = Depends(deps.get_query_engine),
) -> List[Dict[str, Any]]:
    """Execute an arbitrary Cypher query and return the result set."""
    return engine.execute_cypher(cypher)


@router.post("/analytics/shortest_path")
async def api_shortest_path(
    req: ShortestPathRequest,
    perm_graph: PermissionsGraphAdapter = Depends(deps.get_permissions_graph),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Return the shortest path between two nodes."""

    await _ensure_viewable(
        req.source, perm_graph, graph, "Source node not found"
    )
    await _ensure_viewable(
        req.target, perm_graph, graph, "Target node not found"
    )
    path = shortest_path(perm_graph, req.source, req.target)
    filtered = filter_low_confidence(path, settings.UME_RELIABILITY_THRESHOLD)
    return {"path": filtered}


@router.post("/analytics/path")
async def api_constrained_path(
    req: PathRequest,
    perm_graph: PermissionsGraphAdapter = Depends(deps.get_permissions_graph),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Find a path subject to optional depth or label constraints."""

    await _ensure_viewable(
        req.source, perm_graph, graph, "Source node not found"
    )
    await _ensure_viewable(
        req.target, perm_graph, graph, "Target node not found"
    )
    raw_path = perm_graph.constrained_path(
        req.source,
        req.target,
        req.max_depth,
        req.edge_label,
        req.since_timestamp,
    )
    threshold = settings.UME_RELIABILITY_THRESHOLD
    nodes = filter_low_confidence(raw_path, threshold)
    return {"path": nodes}


@router.get("/analytics/path/stream")
async def api_constrained_path_stream(
    source: str = Query(...),
    target: str = Query(...),
    max_depth: int | None = Query(None),
    edge_label: str | None = Query(None),
    since_timestamp: int | None = Query(None),
    _: str = Depends(deps.get_current_role),
    perm_graph: PermissionsGraphAdapter = Depends(deps.get_permissions_graph),
    graph: IGraphAdapter = Depends(deps.get_graph),
    __: None = Depends(RateLimiter(times=2, seconds=1)),
) -> EventSourceResponse:
    """Stream path nodes one by one as an SSE feed."""

    await _ensure_viewable(source, perm_graph, graph, "Source node not found")
    await _ensure_viewable(target, perm_graph, graph, "Target node not found")

    async def _gen() -> AsyncGenerator[dict[str, str], None]:
        path = perm_graph.constrained_path(
            source, target, max_depth, edge_label, since_timestamp
        )
        filtered = filter_low_confidence(path, settings.UME_RELIABILITY_THRESHOLD)
        for node in filtered:
            yield {"data": node}
            await asyncio.sleep(0)

    return EventSourceResponse(_gen())


@router.get("/graph/digest/stream")
async def api_graph_digest_stream(
    cursor: int | None = Query(None, ge=0, description="Start streaming from this ledger offset"),
    last_event_id: int | None = Query(None, ge=0, alias="lastEventId"),
    last_event_id_header: int | None = Header(None, alias="Last-Event-ID"),
    max_events: int | None = Query(None, ge=1, description="Optional cap for emitted digest events"),
    _: str = Depends(deps.get_current_role),
) -> EventSourceResponse:
    """Stream ledger-backed graph digest events via SSE with bounded buffering."""

    queue: asyncio.Queue[dict[str, str]] = asyncio.Queue(maxsize=64)
    dropped_events = 0
    stop_event = asyncio.Event()

    resume_from = last_event_id_header if last_event_id_header is not None else last_event_id
    start_offset = max((cursor if cursor is not None else 0), (resume_from + 1) if resume_from is not None else 0)

    async def _producer() -> None:
        nonlocal dropped_events
        next_offset = start_offset
        emitted = 0
        heartbeat_interval_s = 5.0
        last_heartbeat = time.monotonic()
        while not stop_event.is_set():
            batch = event_ledger.range(start=next_offset, limit=100)
            if batch:
                for offset, event in batch:
                    digest = _to_graph_digest(offset, event)
                    frame = {"event": "graph_digest", "id": str(offset), "data": digest.model_dump_json()}
                    if queue.full():
                        try:
                            queue.get_nowait()
                            dropped_events += 1
                        except asyncio.QueueEmpty:
                            pass
                    await queue.put(frame)
                    next_offset = offset + 1
                    emitted += 1
                    if max_events is not None and emitted >= max_events:
                        stop_event.set()
                        break
                if dropped_events > 0:
                    ctrl = GraphDigestControlEvent(
                        kind="backpressure",
                        cursor_offset=next_offset - 1,
                        dropped_events=dropped_events,
                    )
                    await queue.put({"event": "control", "data": ctrl.model_dump_json()})
                    dropped_events = 0
                last_heartbeat = time.monotonic()
            else:
                now = time.monotonic()
                if now - last_heartbeat >= heartbeat_interval_s:
                    heartbeat = GraphDigestControlEvent(
                        kind="heartbeat",
                        cursor_offset=max(next_offset - 1, -1),
                    )
                    await queue.put({"event": "control", "data": heartbeat.model_dump_json()})
                    last_heartbeat = now
                await asyncio.sleep(0.1)

    async def _gen() -> AsyncGenerator[dict[str, str], None]:
        producer_task = asyncio.create_task(_producer())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.2)
                except asyncio.TimeoutError:
                    if stop_event.is_set() and queue.empty():
                        break
                    continue
                yield event
                await asyncio.sleep(0)
                if stop_event.is_set() and queue.empty():
                    break
        finally:
            stop_event.set()
            producer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await producer_task

    return EventSourceResponse(_gen())


@router.post("/analytics/subgraph")
async def api_subgraph(
    req: SubgraphRequest,
    perm_graph: PermissionsGraphAdapter = Depends(deps.get_permissions_graph),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Extract a subgraph starting from ``start`` to the given ``depth``."""

    await _ensure_viewable(
        req.start, perm_graph, graph, "Start node not found"
    )
    sg = perm_graph.extract_subgraph(
        req.start,
        req.depth,
        req.edge_label,
        req.since_timestamp,
    )
    threshold = settings.UME_RELIABILITY_THRESHOLD
    nodes = filter_low_confidence(sg.get("nodes", {}).keys(), threshold)
    sg["nodes"] = {n: sg["nodes"][n] for n in nodes}
    sg["edges"] = [
        e
        for e in sg.get("edges", [])
        if len(filter_low_confidence(e, threshold)) == len(e)
        and e[0] in sg["nodes"]
        and e[1] in sg["nodes"]
    ]
    return sg


@router.post("/redact/node/{node_id}")
async def api_redact_node(
    node_id: str,
    perm_graph: PermissionsGraphAdapter = Depends(deps.get_permissions_graph),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Redact (delete) a node by its ID."""
    perm_graph._require_editor(node_id)
    event = _canonical_command_event(
        event_type="REDACT_NODE",
        node_id=node_id,
        payload={"node_id": node_id},
        metadata=_command_metadata(perm_graph),
    )
    await _ingest_event_dispatch(event, graph)
    return {"status": "ok"}


@router.post("/events/batch")
async def api_post_events_batch(
    events: List[EventRequest] = Body(...),
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: None = Depends(deps.require_token),
) -> Dict[str, Any]:
    """Apply multiple events sequentially to the graph."""
    try:
        payload = [e.to_ingress_dict() for e in events]
        if isinstance(graph, IAsyncGraphAdapter) or inspect.iscoroutinefunction(
            getattr(graph, "add_node", None)
        ):
            for data in payload:
                await ingest_event_async(data, graph)  # type: ignore[arg-type]
        else:
            ingest_events_batch(payload, graph)
    except (EventError, ProcessingError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"status": "ok"}


@router.post("/store/batch")
async def api_store_events_batch(
    events: List[EventRequest] = Body(...),
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: None = Depends(deps.require_token),
) -> Dict[str, Any]:
    """Alias for :func:`api_post_events_batch`."""
    try:
        payload = [e.to_ingress_dict() for e in events]
        if isinstance(graph, IAsyncGraphAdapter) or inspect.iscoroutinefunction(
            getattr(graph, "add_node", None)
        ):
            for data in payload:
                await ingest_event_async(data, graph)  # type: ignore[arg-type]
        else:
            ingest_events_batch(payload, graph)
    except (EventError, ProcessingError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"status": "ok"}


@router.post("/redact/edge")
async def api_redact_edge(
    req: RedactEdgeRequest,
    perm_graph: PermissionsGraphAdapter = Depends(deps.get_permissions_graph),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Redact an edge between two nodes."""
    _require_edge_permissions(perm_graph, req.source, req.target, req.label)
    event = _canonical_command_event(
        event_type="REDACT_EDGE",
        node_id=req.source,
        target_node_id=req.target,
        label=req.label,
        payload={"source_node_id": req.source, "target_node_id": req.target, "label": req.label},
        metadata=_command_metadata(perm_graph),
    )
    await _ingest_event_dispatch(event, graph)
    return {"status": "ok"}


@router.post("/nodes")
async def api_create_node(
    req: NodeCreateRequest,
    perm_graph: PermissionsGraphAdapter = Depends(deps.get_permissions_graph),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Create a node with optional attributes."""
    event = _canonical_command_event(
        event_type="CREATE_NODE",
        node_id=req.id,
        payload={"node_id": req.id, "attributes": req.attributes or {}},
        metadata=_command_metadata(perm_graph),
    )
    await _ingest_event_dispatch(event, graph)
    return {"status": "ok"}


@router.patch("/nodes/{node_id}")
async def api_update_node(
    node_id: str,
    req: NodeUpdateRequest,
    perm_graph: PermissionsGraphAdapter = Depends(deps.get_permissions_graph),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Update attributes of an existing node."""
    perm_graph._require_editor(node_id)
    event = _canonical_command_event(
        event_type="UPDATE_NODE_ATTRIBUTES",
        node_id=node_id,
        payload={"node_id": node_id, "attributes": req.attributes},
        metadata=_command_metadata(perm_graph),
    )
    await _ingest_event_dispatch(event, graph)
    return {"status": "ok"}


@router.delete("/nodes/{node_id}")
async def api_delete_node(
    node_id: str,
    perm_graph: PermissionsGraphAdapter = Depends(deps.get_permissions_graph),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Remove a node from the graph."""
    perm_graph._require_editor(node_id)
    event = _canonical_command_event(
        event_type="REDACT_NODE",
        node_id=node_id,
        payload={},
        metadata=_command_metadata(perm_graph),
    )
    await _ingest_event_dispatch(event, graph)
    return {"status": "ok"}


@router.post("/edges")
async def api_create_edge(
    req: EdgeCreateRequest,
    perm_graph: PermissionsGraphAdapter = Depends(deps.get_permissions_graph),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Create an edge between two nodes."""
    edge_def = DEFAULT_SCHEMA.edge_labels.get(req.label)
    version = edge_def.version if edge_def else None
    attrs = dict(req.attrs or {})
    is_bootstrap_owner = (
        req.label == "OWNED_BY" and req.source in perm_graph._bootstrap_owner_nodes
    )
    if not is_bootstrap_owner and req.label == "OWNED_BY" and not perm_graph._has_permission(
        req.source, "editor"
    ):
        raise AccessDeniedError("OWNED_BY edges must be bootstrapped before an editor exists")
    if not is_bootstrap_owner:
        _require_edge_permissions(perm_graph, req.source, req.target, req.label)
    event = _canonical_command_event(
        event_type="CREATE_EDGE",
        node_id=req.source,
        target_node_id=req.target,
        label=req.label,
        payload={"source_node_id": req.source, "target_node_id": req.target, "label": req.label, "attributes": attrs, "schema_version": version},
        metadata=_command_metadata(perm_graph),
    )
    await _ingest_event_dispatch(event, graph)
    return {"status": "ok"}


@router.delete("/edges/{source}/{target}/{label}")
async def api_delete_edge(
    source: str,
    target: str,
    label: str,
    perm_graph: PermissionsGraphAdapter = Depends(deps.get_permissions_graph),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Delete an edge identified by source, target and label."""
    _require_edge_permissions(perm_graph, source, target, label)
    event = _canonical_command_event(
        event_type="DELETE_EDGE",
        node_id=source,
        target_node_id=target,
        label=label,
        payload={"source_node_id": source, "target_node_id": target, "label": label},
        metadata=_command_metadata(perm_graph),
    )
    await _ingest_event_dispatch(event, graph)
    return {"status": "ok"}


@router.post("/tweets")
async def api_post_tweet(
    req: TweetCreateRequest,
    perm_graph: PermissionsGraphAdapter = Depends(deps.get_permissions_graph),
) -> Dict[str, Any]:
    """Create a tweet node used by the Tweet-bot."""
    node_id = f"tweet:{uuid4()}"
    await _maybe_call(
        perm_graph,
        "add_node",
        node_id,
        {"text": req.text, "timestamp": int(time.time())},
    )
    return {"id": node_id}


@router.post("/documents")
async def api_upload_document(
    req: DocumentUploadRequest,
    perm_graph: PermissionsGraphAdapter = Depends(deps.get_permissions_graph),
) -> Dict[str, Any]:
    """Upload a document for Document Guru."""
    node_id = f"doc:{uuid4()}"
    cleaned = reformat_document(req.content)
    await _maybe_call(
        perm_graph,
        "add_node",
        node_id,
        {"content": cleaned, "timestamp": int(time.time())},
    )
    return {"id": node_id}


@router.get("/documents/{document_id}")
async def api_get_document(
    document_id: str,
    perm_graph: PermissionsGraphAdapter = Depends(deps.get_permissions_graph),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Return a previously uploaded document."""
    doc = await _ensure_viewable(
        document_id, perm_graph, graph, "Document not found"
    )
    return {"id": document_id, "content": doc.get("content", "")}


@router.get("/entities/{type}/{id}")
async def api_get_entity(
    id: str,
    entity: Dict[str, Any] = Depends(deps.get_entity),
) -> Dict[str, Any]:
    """Return node ``id`` if its ``type`` matches the path parameter."""
    return {"id": id, "attributes": entity}


@router.get("/events")
def api_get_events(
    tag: str | None = Query(None),
    node_id: str | None = Query(None),
    limit: int = Query(100, ge=1),
    _: str = Depends(deps.get_current_role),
    engine: Neo4jQueryEngine = Depends(deps.get_query_engine),
) -> List[Dict[str, Any]]:
    """Query events filtered by optional ``tag`` or ``node_id``."""

    cypher, params = build_events_query(tag=tag, node_id=node_id, limit=limit)
    return engine.execute_cypher(cypher, params)


@router.post("/events")
async def api_post_event(
    req: EventRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: None = Depends(deps.require_token),
) -> Dict[str, Any]:
    """Validate and apply an event to the graph."""
    try:
        data = req.to_ingress_dict()
        if isinstance(graph, IAsyncGraphAdapter) or inspect.iscoroutinefunction(
            getattr(graph, "add_node", None)
        ):
            await ingest_event_async(data, graph)  # type: ignore[arg-type]
        else:
            ingest_event(data, graph)
    except (EventError, ProcessingError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"status": "ok"}


@router.post("/store")
async def api_store_event(
    req: EventRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: None = Depends(deps.require_token),
) -> Dict[str, Any]:
    """Alias for :func:`api_post_event`."""
    try:
        data = req.to_ingress_dict()
        if isinstance(graph, IAsyncGraphAdapter) or inspect.iscoroutinefunction(
            getattr(graph, "add_node", None)
        ):
            await ingest_event_async(data, graph)  # type: ignore[arg-type]
        else:
            ingest_event(data, graph)
    except (EventError, ProcessingError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"status": "ok"}
