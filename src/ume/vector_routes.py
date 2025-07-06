from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from . import api_deps as deps
from .vector_backends import VectorStore
from .graph_adapter import IGraphAdapter
from .embedding import generate_embedding

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


@router.get("/recall")
def api_recall(
    query: str | None = Query(None),
    vector: List[float] | None = Query(None),
    k: int = 5,
    _: str = Depends(deps.get_current_role),
    store: VectorStore = Depends(deps.get_vector_store),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> Dict[str, Any]:
    """Return attributes for the ``k`` nearest nodes to ``query`` or ``vector``."""
    if query is None and vector is None:
        raise HTTPException(status_code=400, detail="query or vector required")
    if vector is None and query is not None:
        vector = generate_embedding(query)
    assert vector is not None
    if len(vector) != store.dim:
        raise HTTPException(status_code=400, detail="Invalid vector dimension")
    ids = store.query(vector, k=k)
    nodes = []
    for node_id in ids:
        attrs = graph.get_node(node_id)
        if attrs is not None:
            nodes.append({"id": node_id, "attributes": attrs})
    return {"nodes": nodes}


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

