from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from .audit import get_audit_entries
from .graph_adapter import IGraphAdapter
from .api_deps import get_current_role, get_graph, get_vector_store
from .vector_backends import VectorStore

router = APIRouter(prefix="/dashboard")


@router.get("/stats")
def dashboard_stats(
    _: str = Depends(get_current_role),
    graph: IGraphAdapter = Depends(get_graph),
    store: VectorStore = Depends(get_vector_store),
) -> Dict[str, Any]:
    node_count = len(graph.get_all_node_ids())
    edge_count = len(graph.get_all_edges())
    index_size = len(getattr(store, "idx_to_id", []))
    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "vector_index_size": index_size,
    }


@router.get("/recent_events")
def dashboard_recent_events(
    limit: int = 10,
    _: str = Depends(get_current_role),
) -> List[Dict[str, Any]]:
    entries = get_audit_entries()
    return list(reversed(entries[-limit:]))
