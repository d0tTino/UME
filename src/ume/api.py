"""HTTP API exposing graph queries and analytics."""

from __future__ import annotations

from .config import settings
import os
from typing import Any, Dict, List

from fastapi import Depends, FastAPI, HTTPException, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .analytics import shortest_path
from .rbac_adapter import RoleBasedGraphAdapter, AccessDeniedError
from .graph_adapter import IGraphAdapter
from .query import Neo4jQueryEngine

API_TOKEN = settings.UME_API_TOKEN

app = FastAPI()

# These can be configured by the embedding application or tests
app.state.query_engine = None  # type: ignore[assignment]
app.state.graph = None  # type: ignore[assignment]
app.state.vector_index = {}  # type: ignore[assignment]


def configure_graph(graph: IGraphAdapter) -> None:
    """Set ``app.state.graph`` applying RBAC if ``UME_API_ROLE`` is defined."""
    role = os.getenv("UME_API_ROLE")
    if role:
        graph = RoleBasedGraphAdapter(graph, role=role)
    app.state.graph = graph


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


def get_vector_index() -> Dict[str, List[float]]:
    index = app.state.vector_index
    if index is None:
        raise HTTPException(status_code=500, detail="Vector index not configured")
    return index


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
    path = shortest_path(graph, req.source, req.target)
    return {"path": path}


@app.post("/analytics/path")
def api_constrained_path(
    req: PathRequest,
    _: None = Depends(require_token),
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
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
    graph.redact_edge(req.source, req.target, req.label)
    return {"status": "ok"}


@app.post("/nodes")
def api_create_node(
    req: NodeCreateRequest,
    _: None = Depends(require_token),
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    graph.add_node(req.id, req.attributes or {})
    return {"status": "ok"}


@app.patch("/nodes/{node_id}")
def api_update_node(
    node_id: str,
    req: NodeUpdateRequest,
    _: None = Depends(require_token),
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    graph.update_node(node_id, req.attributes)
    return {"status": "ok"}


@app.delete("/nodes/{node_id}")
def api_delete_node(
    node_id: str,
    _: None = Depends(require_token),
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    graph.redact_node(node_id)
    return {"status": "ok"}


@app.post("/edges")
def api_create_edge(
    req: EdgeCreateRequest,
    _: None = Depends(require_token),
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
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
    graph.delete_edge(source, target, label)
    return {"status": "ok"}


class VectorAddRequest(BaseModel):
    id: str
    vector: List[float]


@app.post("/vectors")
def api_add_vector(
    req: VectorAddRequest,
    _: None = Depends(require_token),
    index: Dict[str, List[float]] = Depends(get_vector_index),
) -> Dict[str, Any]:
    index[req.id] = req.vector
    return {"status": "ok"}


@app.get("/vectors/search")
def api_search_vectors(
    vector: List[float] = Query(...),
    k: int = 5,
    _: None = Depends(require_token),
    index: Dict[str, List[float]] = Depends(get_vector_index),
) -> Dict[str, Any]:
    def _dist(v: List[float]) -> float:
        return sum((a - b) ** 2 for a, b in zip(v, vector)) ** 0.5

    neighbors = sorted(index.items(), key=lambda item: _dist(item[1]))[:k]
    return {"ids": [nid for nid, _ in neighbors]}
