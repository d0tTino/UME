from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator, Dict, List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi_limiter.depends import RateLimiter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .analytics import shortest_path
from .config import settings
from .document_guru import reformat_document
from .reliability import filter_low_confidence
import inspect
from .graph_adapter import IGraphAdapter
from .async_graph_adapter import IAsyncGraphAdapter, ingest_event_async
from .query import Neo4jQueryEngine, build_events_query
from .event import EventError
from .processing import ProcessingError
from ume.services.ingest import ingest_event, ingest_events_batch

# import shared API dependencies
from . import api_deps as deps

router = APIRouter()


async def _maybe_call(graph: IGraphAdapter, name: str, *args: Any) -> Any:
    func = getattr(graph, name)
    if inspect.iscoroutinefunction(func) or isinstance(graph, IAsyncGraphAdapter):
        result = await func(*args)
    else:
        result = func(*args)
    if inspect.isawaitable(result):
        result = await result
    return result


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

    eventType: str
    timestamp: int
    eventId: str | None = None
    sourceService: str | None = None
    node_id: str | None = None
    target_node_id: str | None = None
    label: str | None = None
    payload: Dict[str, Any] | None = None
    

@router.get("/query")
def run_cypher(
    cypher: str,
    _: str = Depends(deps.get_current_role),
    engine: Neo4jQueryEngine = Depends(deps.get_query_engine),
) -> List[Dict[str, Any]]:
    """Execute an arbitrary Cypher query and return the result set."""
    return engine.execute_cypher(cypher)


@router.post("/analytics/shortest_path")
def api_shortest_path(
    req: ShortestPathRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Return the shortest path between two nodes."""
    path = shortest_path(graph, req.source, req.target)
    filtered = filter_low_confidence(path, settings.UME_RELIABILITY_THRESHOLD)
    return {"path": filtered}


@router.post("/analytics/path")
def api_constrained_path(
    req: PathRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Find a path subject to optional depth or label constraints."""
    raw_path = graph.constrained_path(
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
    graph: IGraphAdapter = Depends(deps.get_graph),
    __: None = Depends(RateLimiter(times=2, seconds=1)),
) -> EventSourceResponse:
    """Stream path nodes one by one as an SSE feed."""

    async def _gen() -> AsyncGenerator[dict[str, str], None]:
        path = graph.constrained_path(
            source, target, max_depth, edge_label, since_timestamp
        )
        filtered = filter_low_confidence(path, settings.UME_RELIABILITY_THRESHOLD)
        for node in filtered:
            yield {"data": node}
            await asyncio.sleep(0)

    return EventSourceResponse(_gen())


@router.post("/analytics/subgraph")
def api_subgraph(
    req: SubgraphRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Extract a subgraph starting from ``start`` to the given ``depth``."""
    sg = graph.extract_subgraph(
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
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Redact (delete) a node by its ID."""
    await _maybe_call(graph, "redact_node", node_id)
    return {"status": "ok"}


@router.post("/events/batch")
async def api_post_events_batch(
    events: List[EventRequest] = Body(...),
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: None = Depends(deps.require_token),
) -> Dict[str, Any]:
    """Apply multiple events sequentially to the graph."""
    try:
        payload = [e.model_dump(exclude_none=True) for e in events]
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
        payload = [e.model_dump(exclude_none=True) for e in events]
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
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Redact an edge between two nodes."""
    await _maybe_call(graph, "redact_edge", req.source, req.target, req.label)
    return {"status": "ok"}


@router.post("/nodes")
async def api_create_node(
    req: NodeCreateRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Create a node with optional attributes."""
    await _maybe_call(graph, "add_node", req.id, req.attributes or {})
    return {"status": "ok"}


@router.patch("/nodes/{node_id}")
async def api_update_node(
    node_id: str,
    req: NodeUpdateRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Update attributes of an existing node."""
    await _maybe_call(graph, "update_node", node_id, req.attributes)
    return {"status": "ok"}


@router.delete("/nodes/{node_id}")
async def api_delete_node(
    node_id: str,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Remove a node from the graph."""
    await _maybe_call(graph, "redact_node", node_id)
    return {"status": "ok"}


@router.post("/edges")
async def api_create_edge(
    req: EdgeCreateRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Create an edge between two nodes."""
    await _maybe_call(graph, "add_edge", req.source, req.target, req.label)
    return {"status": "ok"}


@router.delete("/edges/{source}/{target}/{label}")
async def api_delete_edge(
    source: str,
    target: str,
    label: str,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Delete an edge identified by source, target and label."""
    await _maybe_call(graph, "delete_edge", source, target, label)
    return {"status": "ok"}


@router.post("/tweets")
async def api_post_tweet(
    req: TweetCreateRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Create a tweet node used by the Tweet-bot."""
    node_id = f"tweet:{uuid4()}"
    await _maybe_call(
        graph,
        "add_node",
        node_id,
        {"text": req.text, "timestamp": int(time.time())},
    )
    return {"id": node_id}


@router.post("/documents")
async def api_upload_document(
    req: DocumentUploadRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Upload a document for Document Guru."""
    node_id = f"doc:{uuid4()}"
    cleaned = reformat_document(req.content)
    await _maybe_call(
        graph,
        "add_node",
        node_id,
        {"content": cleaned, "timestamp": int(time.time())},
    )
    return {"id": node_id}


@router.get("/documents/{document_id}")
async def api_get_document(
    document_id: str,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Return a previously uploaded document."""
    doc = await _maybe_call(graph, "get_node", document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
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
        data = req.model_dump(exclude_none=True)
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
        data = req.model_dump(exclude_none=True)
        if isinstance(graph, IAsyncGraphAdapter) or inspect.iscoroutinefunction(
            getattr(graph, "add_node", None)
        ):
            await ingest_event_async(data, graph)  # type: ignore[arg-type]
        else:
            ingest_event(data, graph)
    except (EventError, ProcessingError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"status": "ok"}

