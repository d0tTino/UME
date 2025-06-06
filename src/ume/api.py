"""HTTP API exposing graph queries and analytics."""
from __future__ import annotations

import os
from typing import Any, Dict, List

from fastapi import Depends, FastAPI, HTTPException, Header
from pydantic import BaseModel

from .analytics import shortest_path
from .graph_adapter import IGraphAdapter
from .query import Neo4jQueryEngine

API_TOKEN = os.environ.get("UME_API_TOKEN", "secret-token")

app = FastAPI()

# These can be configured by the embedding application or tests
app.state.query_engine = None  # type: ignore[assignment]
app.state.graph = None  # type: ignore[assignment]


def require_token(authorization: str | None = Header(default=None)) -> None:
    """Simple token-based auth using the Authorization header."""
    if authorization is None or authorization != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")


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


@app.get("/query")
def run_cypher(cypher: str, _: None = Depends(require_token), engine: Neo4jQueryEngine = Depends(get_query_engine)) -> List[Dict[str, Any]]:
    """Execute an arbitrary Cypher query and return the result set."""
    return engine.execute_cypher(cypher)


class ShortestPathRequest(BaseModel):
    source: str
    target: str


@app.post("/analytics/shortest_path")
def api_shortest_path(req: ShortestPathRequest, _: None = Depends(require_token), graph: IGraphAdapter = Depends(get_graph)) -> Dict[str, Any]:
    path = shortest_path(graph, req.source, req.target)
    return {"path": path}


@app.post("/redact/node/{node_id}")
def api_redact_node(node_id: str, _: None = Depends(require_token), graph: IGraphAdapter = Depends(get_graph)) -> Dict[str, Any]:
    graph.redact_node(node_id)
    return {"status": "ok"}


class RedactEdgeRequest(BaseModel):
    source: str
    target: str
    label: str


@app.post("/redact/edge")
def api_redact_edge(req: RedactEdgeRequest, _: None = Depends(require_token), graph: IGraphAdapter = Depends(get_graph)) -> Dict[str, Any]:
    graph.redact_edge(req.source, req.target, req.label)
    return {"status": "ok"}
