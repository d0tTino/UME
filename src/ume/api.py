"""HTTP API exposing graph queries and analytics."""

from __future__ import annotations

from .config import settings
import os
from .logging_utils import configure_logging
from typing import Any, Dict, List

import time
from fastapi import Depends, FastAPI, HTTPException, Header, Query, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    REGISTRY,
)
from pydantic import BaseModel

from .analytics import shortest_path
from .rbac_adapter import RoleBasedGraphAdapter, AccessDeniedError
from .graph_adapter import IGraphAdapter
from .query import Neo4jQueryEngine
from .vector_store import VectorStore, create_default_store


def _existing_metric(name: str):
    """Return a previously registered metric by name if present."""
    return REGISTRY._names_to_collectors.get(name)

configure_logging()

API_TOKEN = settings.UME_API_TOKEN

app = FastAPI(
    title="UME API",
    version="0.1.0",
    description="HTTP API for the Universal Memory Engine.",
)

REQUEST_COUNT = _existing_metric("ume_http_requests_total") or Counter(
    "ume_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = _existing_metric("ume_request_latency_seconds") or Histogram(
    "ume_request_latency_seconds",
    "Request latency in seconds",
    ["method", "path"],
)

# Metrics for vector search operations
VECTOR_QUERY_LATENCY = _existing_metric(
    "ume_vector_query_latency_seconds"
) or Histogram(
    "ume_vector_query_latency_seconds",
    "VectorStore query latency in seconds",
)
VECTOR_INDEX_SIZE = _existing_metric("ume_vector_index_size") or Gauge(
    "ume_vector_index_size",
    "Number of vectors stored in the VectorStore",
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    method = request.method
    path = request.url.path
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        REQUEST_LATENCY.labels(method=method, path=path).observe(
            time.perf_counter() - start
        )
        REQUEST_COUNT.labels(method=method, path=path, status="500").inc()
        raise
    REQUEST_LATENCY.labels(method=method, path=path).observe(
        time.perf_counter() - start
    )
    REQUEST_COUNT.labels(method=method, path=path, status=str(response.status_code)).inc()
    return response

# These can be configured by the embedding application or tests
app.state.query_engine = None  # type: ignore[assignment]
app.state.graph = None  # type: ignore[assignment]
try:
    app.state.vector_store = create_default_store()  # type: ignore[assignment]
except ModuleNotFoundError:
    app.state.vector_store = None


def configure_graph(graph: IGraphAdapter) -> None:
    """Set ``app.state.graph`` applying RBAC if ``UME_API_ROLE`` is defined."""
    role = os.getenv("UME_API_ROLE")
    if role:
        graph = RoleBasedGraphAdapter(graph, role=role)
    app.state.graph = graph


def configure_vector_store(store: VectorStore) -> None:
    """Inject a :class:`VectorStore` instance into the application state."""
    app.state.vector_store = store


@app.exception_handler(AccessDeniedError)
async def access_denied_handler(request, exc: AccessDeniedError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


def require_token(authorization: str | None = Header(default=None)) -> None:
    """Simple token-based auth using the Authorization header."""
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    auth_header = authorization.strip()
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Malformed Authorization header")

    token = auth_header[7:].strip()  # len("Bearer ") == 7
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API token")


def get_query_engine() -> Neo4jQueryEngine:
    engine = app.state.query_engine
    if engine is None:
        raise HTTPException(status_code=500, detail="Query engine not configured")
    return engine


def get_graph() -> IGraphAdapter:
    graph = app.state.graph
    if graph is None:
        raise HTTPException(status_code=500, detail="Graph not configured")
    return graph


def get_vector_store() -> VectorStore:
    store = app.state.vector_store
    if store is None:
        raise HTTPException(status_code=500, detail="Vector store not configured")
    return store


@app.get("/query")
def run_cypher(
    cypher: str,
    _: None = Depends(require_token),
    engine: Neo4jQueryEngine = Depends(get_query_engine),
) -> List[Dict[str, Any]]:
    """Execute an arbitrary Cypher query and return the result set."""
    return engine.execute_cypher(cypher)


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


@app.post("/analytics/shortest_path")
def api_shortest_path(
    req: ShortestPathRequest,
    _: None = Depends(require_token),
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Return the shortest path between two nodes."""
    path = shortest_path(graph, req.source, req.target)
    return {"path": path}


@app.post("/analytics/path")
def api_constrained_path(
    req: PathRequest,
    _: None = Depends(require_token),
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Find a path subject to optional depth or label constraints."""
    path = graph.constrained_path(
        req.source,
        req.target,
        req.max_depth,
        req.edge_label,
        req.since_timestamp,
    )
    return {"path": path}


@app.post("/analytics/subgraph")
def api_subgraph(
    req: SubgraphRequest,
    _: None = Depends(require_token),
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Extract a subgraph starting from ``start`` to the given ``depth``."""
    return graph.extract_subgraph(
        req.start,
        req.depth,
        req.edge_label,
        req.since_timestamp,
    )


@app.post("/redact/node/{node_id}")
def api_redact_node(
    node_id: str,
    _: None = Depends(require_token),
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Redact (delete) a node by its ID."""
    graph.redact_node(node_id)
    return {"status": "ok"}


class RedactEdgeRequest(BaseModel):
    source: str
    target: str
    label: str


@app.post("/redact/edge")
def api_redact_edge(
    req: RedactEdgeRequest,
    _: None = Depends(require_token),
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Redact an edge between two nodes."""
    graph.redact_edge(req.source, req.target, req.label)
    return {"status": "ok"}


@app.post("/nodes")
def api_create_node(
    req: NodeCreateRequest,
    _: None = Depends(require_token),
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Create a node with optional attributes."""
    graph.add_node(req.id, req.attributes or {})
    return {"status": "ok"}


@app.patch("/nodes/{node_id}")
def api_update_node(
    node_id: str,
    req: NodeUpdateRequest,
    _: None = Depends(require_token),
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Update attributes of an existing node."""
    graph.update_node(node_id, req.attributes)
    return {"status": "ok"}


@app.delete("/nodes/{node_id}")
def api_delete_node(
    node_id: str,
    _: None = Depends(require_token),
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Remove a node from the graph."""
    graph.redact_node(node_id)
    return {"status": "ok"}


@app.post("/edges")
def api_create_edge(
    req: EdgeCreateRequest,
    _: None = Depends(require_token),
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Create an edge between two nodes."""
    graph.add_edge(req.source, req.target, req.label)
    return {"status": "ok"}


@app.delete("/edges/{source}/{target}/{label}")
def api_delete_edge(
    source: str,
    target: str,
    label: str,
    _: None = Depends(require_token),
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Delete an edge identified by source, target and label."""
    graph.delete_edge(source, target, label)
    return {"status": "ok"}


class VectorAddRequest(BaseModel):
    id: str
    vector: List[float]


@app.post("/vectors")
def api_add_vector(
    req: VectorAddRequest,
    _: None = Depends(require_token),
    store: VectorStore = Depends(get_vector_store),
) -> Dict[str, Any]:
    """Store an embedding vector for later similarity search."""
    store.add(req.id, req.vector)
    return {"status": "ok"}


@app.get("/vectors/search")
def api_search_vectors(
    vector: List[float] = Query(...),
    k: int = 5,
    _: None = Depends(require_token),
    store: VectorStore = Depends(get_vector_store),
) -> Dict[str, Any]:
    """Find the IDs of the ``k`` nearest vectors to ``vector``."""
    ids = store.query(vector, k=k)
    return {"ids": ids}


@app.get("/metrics")
def metrics_endpoint() -> Response:
    """Expose Prometheus metrics."""
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
