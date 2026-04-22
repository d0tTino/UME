from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException

from . import api_deps as deps
from .kernel.graph_adapter import IGraphAdapter
from .permissions_adapter import PermissionsGraphAdapter
from .utils import ensure_group_member

router = APIRouter(prefix="/v1/nodes")


@router.get("")
def get_nodes_by_user(
    perm_graph: PermissionsGraphAdapter = Depends(deps.get_permissions_graph),
    _: str = Depends(deps.get_current_role),
) -> Dict[str, List[str]]:
    """Return nodes owned by the specified user."""

    user_id = perm_graph.user_id
    if user_id is None:
        raise HTTPException(status_code=400, detail="user_id is required")
    node_ids = perm_graph.get_nodes_by_user(user_id)
    return {"nodes": node_ids}


@router.get("/shared")
def get_nodes_shared_with(
    perm_graph: PermissionsGraphAdapter = Depends(deps.get_permissions_graph),
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: str = Depends(deps.get_current_role),
) -> Dict[str, List[str]]:
    """Return nodes shared with the specified group."""

    user_id = perm_graph.user_id
    group_id = perm_graph.group_id
    if user_id is None:
        raise HTTPException(status_code=400, detail="user_id is required")
    if group_id is None:
        raise HTTPException(status_code=400, detail="group_id is required")
    ensure_group_member(graph, user_id, group_id)
    node_ids = perm_graph.get_nodes_shared_with(group_id)
    return {"nodes": node_ids}
