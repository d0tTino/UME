from __future__ import annotations

from typing import Any, Dict, List, AsyncGenerator
import asyncio
import json
import math
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import api_deps as deps
from .permissions_adapter import PermissionsGraphAdapter
from .vector_store import VectorStore
from .graph_routes import _maybe_call
from . import embedding
from .metrics import (
    RECALL_SCORE,
    RECALL_LATENCY,
    RECALL_LATENCY_MS,
    SEMANTIC_SEARCH_LATENCY,
)

router = APIRouter()


class VectorAddRequest(BaseModel):
    id: str
    vector: List[float]


@router.post("/vectors")
def api_add_vector(
    req: VectorAddRequest,
    _: str = Depends(deps.get_current_role),
    store: VectorStore = Depends(deps.get_vector_store),
) -> Dict[str, Any]:
    """Store an embedding vector for later similarity search."""
    if len(req.vector) != store.dim:
        raise HTTPException(status_code=400, detail="Invalid vector dimension")
    store.add(req.id, req.vector)
    return {"status": "ok"}


@router.get("/vectors/search")
def api_search_vectors(
    vector: List[float] = Query(...),
    k: int = 5,
    _: str = Depends(deps.get_current_role),
    store: VectorStore = Depends(deps.get_vector_store),
) -> Dict[str, Any]:
    """Find the IDs of the ``k`` nearest vectors to ``vector``."""
    if len(vector) != store.dim:
        raise HTTPException(status_code=400, detail="Invalid vector dimension")
    ids = store.query(vector, k=k)
    return {"ids": ids}


class SemanticSearchRequest(BaseModel):
    query: str
    k: int = 5


@router.post("/search/semantic")
async def api_semantic_search(
    req: SemanticSearchRequest,
    _: str = Depends(deps.get_current_role),
    store: VectorStore = Depends(deps.get_vector_store),
    perm_graph: PermissionsGraphAdapter = Depends(deps.get_permissions_graph),
) -> Dict[str, Any]:
    """Return attributes for the ``k`` nearest nodes to ``req.query``."""
    start = time.perf_counter()
    vector = embedding.generate_embedding(req.query)
    if len(vector) != store.dim:
        raise HTTPException(status_code=400, detail="Invalid vector dimension")
    if req.k <= 0:
        raise HTTPException(status_code=400, detail="k must be positive")
    ids = store.query(vector, k=req.k)
    nodes = []
    for node_id in ids:
        attrs = await _maybe_call(perm_graph, "get_node", node_id)
        if attrs is not None:
            nodes.append({"id": node_id, "attributes": attrs})
    SEMANTIC_SEARCH_LATENCY.observe(time.perf_counter() - start)
    return {"nodes": nodes}


@router.get("/recall")
async def api_recall(
    query: str | None = Query(None),
    vector: List[float] | None = Query(None),
    k: int = 5,
    _: str = Depends(deps.get_current_role),
    store: VectorStore = Depends(deps.get_vector_store),
    perm_graph: PermissionsGraphAdapter = Depends(deps.get_permissions_graph),
) -> Dict[str, Any]:
    """Return attributes for the ``k`` nearest nodes to ``query`` or ``vector``."""
    if query is None and vector is None:
        raise HTTPException(status_code=400, detail="query or vector required")
    if vector is None and query is not None:
        vector = embedding.generate_embedding(query)
    assert vector is not None
    if len(vector) != store.dim:
        raise HTTPException(status_code=400, detail="Invalid vector dimension")
    start = time.perf_counter()
    ids = store.query(vector, k=k)
    nodes = []
    for node_id in ids:
        attrs = await _maybe_call(perm_graph, "get_node", node_id)
        if attrs is None:
            continue
        emb = attrs.get("embedding")
        if isinstance(emb, list) and len(emb) == len(vector):
            try:
                RECALL_SCORE.observe(math.dist(vector, emb))
            except TypeError:
                pass
        nodes.append({"id": node_id, "attributes": attrs})
    duration = time.perf_counter() - start
    RECALL_LATENCY.observe(duration)
    RECALL_LATENCY_MS.observe(duration * 1000)
    return {"nodes": nodes}


@router.get("/recall/stream")
async def api_recall_stream(
    query: str | None = Query(None),
    vector: List[float] | None = Query(None),
    k: int = 5,
    _: str = Depends(deps.get_current_role),
    store: VectorStore = Depends(deps.get_vector_store),
    perm_graph: PermissionsGraphAdapter = Depends(deps.get_permissions_graph),
) -> StreamingResponse:
    """Stream nearest nodes one by one as they are found."""
    if query is None and vector is None:
        raise HTTPException(status_code=400, detail="query or vector required")
    if vector is None and query is not None:
        vector = embedding.generate_embedding(query)
    assert vector is not None
    if len(vector) != store.dim:
        raise HTTPException(status_code=400, detail="Invalid vector dimension")

    async def _gen() -> AsyncGenerator[str, None]:
        start = time.perf_counter()
        ids = store.query(vector, k=k)
        for node_id in ids:
            attrs = await _maybe_call(perm_graph, "get_node", node_id)
            if attrs is None:
                await asyncio.sleep(0)
                continue
            emb = attrs.get("embedding")
            if isinstance(emb, list) and len(emb) == len(vector):
                try:
                    RECALL_SCORE.observe(math.dist(vector, emb))
                except TypeError:
                    pass
            payload = {"id": node_id, "attributes": attrs}
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0)
        duration = time.perf_counter() - start
        RECALL_LATENCY.observe(duration)
        RECALL_LATENCY_MS.observe(duration * 1000)

    return StreamingResponse(_gen(), media_type="text/event-stream")


@router.get("/vectors/benchmark")
def api_benchmark_vectors(
    use_gpu: bool = Query(False),
    num_vectors: int = 1000,
    num_queries: int = 100,
    runs: int = 1,
    _: str = Depends(deps.get_current_role),
    store: VectorStore = Depends(deps.get_vector_store),
) -> Dict[str, Any]:
    """Run a synthetic benchmark against the vector store."""
    from .benchmarks import benchmark_vector_store

    return benchmark_vector_store(
        use_gpu,
        dim=store.dim,
        num_vectors=num_vectors,
        num_queries=num_queries,
        runs=runs,
    )

