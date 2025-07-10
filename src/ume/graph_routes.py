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
from .graph_adapter import IGraphAdapter
from .query import Neo4jQueryEngine
from .event import EventError
from .processing import ProcessingError
from ume.services.ingest import ingest_event, ingest_events_batch

# import shared API dependencies
from . import api_deps as deps

router = APIRouter()


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
def api_redact_node(
    node_id: str,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Redact (delete) a node by its ID."""
    graph.redact_node(node_id)
    return {"status": "ok"}


@router.post("/events/batch")
def api_post_events_batch(
    events: List[Dict[str, Any]] = Body(...),
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: None = Depends(deps.require_token),
) -> Dict[str, Any]:
    """Apply multiple events sequentially to the graph."""
    try:
        ingest_events_batch(events, graph)
    except (EventError, ProcessingError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"status": "ok"}


@router.post("/redact/edge")
def api_redact_edge(
    req: RedactEdgeRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Redact an edge between two nodes."""
    graph.redact_edge(req.source, req.target, req.label)
    return {"status": "ok"}


@router.post("/nodes")
def api_create_node(
    req: NodeCreateRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Create a node with optional attributes."""
    graph.add_node(req.id, req.attributes or {})
    return {"status": "ok"}


@router.patch("/nodes/{node_id}")
def api_update_node(
    node_id: str,
    req: NodeUpdateRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Update attributes of an existing node."""
    graph.update_node(node_id, req.attributes)
    return {"status": "ok"}


@router.delete("/nodes/{node_id}")
def api_delete_node(
    node_id: str,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Remove a node from the graph."""
    graph.redact_node(node_id)
    return {"status": "ok"}


@router.post("/edges")
def api_create_edge(
    req: EdgeCreateRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Create an edge between two nodes."""
    graph.add_edge(req.source, req.target, req.label)
    return {"status": "ok"}


@router.delete("/edges/{source}/{target}/{label}")
def api_delete_edge(
    source: str,
    target: str,
    label: str,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Delete an edge identified by source, target and label."""
    graph.delete_edge(source, target, label)
    return {"status": "ok"}


@router.post("/tweets")
def api_post_tweet(
    req: TweetCreateRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Create a tweet node used by the Tweet-bot."""
    node_id = f"tweet:{uuid4()}"
    graph.add_node(node_id, {"text": req.text, "timestamp": int(time.time())})
    return {"id": node_id}


@router.post("/documents")
def api_upload_document(
    req: DocumentUploadRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Upload a document for Document Guru."""
    node_id = f"doc:{uuid4()}"
    cleaned = reformat_document(req.content)
    graph.add_node(node_id, {"content": cleaned, "timestamp": int(time.time())})
    return {"id": node_id}


@router.get("/documents/{document_id}")
def api_get_document(
    document_id: str,
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Return a previously uploaded document."""
    doc = graph.get_node(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"id": document_id, "content": doc.get("content", "")}


@router.post("/events")
def api_post_event(
    data: Dict[str, Any] = Body(...),
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: None = Depends(deps.require_token),
) -> Dict[str, Any]:
    """Validate and apply an event to the graph."""
    try:
        ingest_event(data, graph)
    except (EventError, ProcessingError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"status": "ok"}

