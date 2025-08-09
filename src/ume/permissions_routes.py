from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends, Query

from . import api_deps as deps
from .graph_adapter import IGraphAdapter
from .permissions_adapter import PermissionsGraphAdapter

router = APIRouter(prefix="/v1/nodes")


@router.get("")
def get_nodes_by_user(
    user_id: str = Query(...),
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: str = Depends(deps.get_current_role),
) -> Dict[str, List[str]]:
    """Return nodes owned by the specified user."""
    perm_graph = PermissionsGraphAdapter(graph, user_id=user_id)
    node_ids = perm_graph.get_nodes_by_user(user_id)
    return {"nodes": node_ids}


@router.get("/shared")
def get_nodes_shared_with(
    group_id: str = Query(...),
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: str = Depends(deps.get_current_role),
) -> Dict[str, List[str]]:
    """Return nodes shared with the specified group."""
    perm_graph = PermissionsGraphAdapter(graph, group_id=group_id)
    node_ids = perm_graph.get_nodes_shared_with(group_id)
    return {"nodes": node_ids}
