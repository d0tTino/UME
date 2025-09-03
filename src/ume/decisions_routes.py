from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from . import api_deps as deps
from .graph_adapter import IGraphAdapter
from .permissions_adapter import PermissionsGraphAdapter
from .rbac_adapter import AccessDeniedError
from .utils import ensure_group_member
from .models import (
    DecisionAnalysis,
    ProposedAction,
    create_decision_analysis,
    create_proposed_action,
)

EDGE_VERSION = "3.0.0"

router = APIRouter(prefix="/v1/decisions")


class DecisionCreateRequest(BaseModel):
    query: str
    user_id: str
    group_id: str | None = None


class ActionCreateRequest(BaseModel):
    description: str
    rank: int = 0
    is_optimal: bool = False
    outcome_metrics: dict[str, float] | None = None
    user_id: str
    group_id: str | None = None


def _analysis_to_dict(analysis: DecisionAnalysis) -> dict[str, Any]:
    return {
        "analysis_id": analysis.analysis_id,
        "query": analysis.query,
        "created_at": int(analysis.created_at.timestamp()),
        "schema_version": analysis.schema_version,
    }


def _action_to_dict(action: ProposedAction) -> dict[str, Any]:
    return {
        "action_id": action.action_id,
        "description": action.description,
        "rank": action.rank,
        "is_optimal": action.is_optimal,
        "outcome_metrics": action.outcome_metrics,
        "schema_version": action.schema_version,
    }


@router.post("")
def create_decision(
    req: DecisionCreateRequest,
    _: str = Depends(deps.get_current_role),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> dict[str, Any]:
    if req.group_id:
        ensure_group_member(graph, req.user_id, req.group_id)
    perm_graph = PermissionsGraphAdapter(
        graph, user_id=req.user_id, group_id=req.group_id
    )
    analysis = create_decision_analysis(req.query)
    attrs = _analysis_to_dict(analysis)
    perm_graph.add_node(analysis.analysis_id, attrs)
    # Ensure subject nodes exist
    if not graph.node_exists(req.user_id):
        graph.add_node(req.user_id, {})
    # Link analysis to the owning user
    graph.add_edge(
        analysis.analysis_id,
        req.user_id,
        "OWNED_BY",
        {"permission_level": "editor"},
        schema_version=EDGE_VERSION,
    )
    perm_graph.rebuild_index()
    if req.group_id:
        if not graph.node_exists(req.group_id):
            graph.add_node(req.group_id, {})
        perm_graph.add_edge(
            analysis.analysis_id,
            req.group_id,
            "SHARED_WITH",
            {"permission_level": "editor"},
        )
    return attrs


@router.post("/{analysis_id}/actions")
def add_action(
    analysis_id: str,
    req: ActionCreateRequest,
    _: str = Depends(deps.get_current_role),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> dict[str, Any]:
    if req.group_id:
        ensure_group_member(graph, req.user_id, req.group_id)
    perm_graph = PermissionsGraphAdapter(
        graph, user_id=req.user_id, group_id=req.group_id
    )
    if not perm_graph.node_exists(analysis_id):
        raise HTTPException(status_code=404, detail="Analysis not found")
    action = create_proposed_action(
        req.description,
        rank=req.rank,
        is_optimal=req.is_optimal,
        outcome_metrics=req.outcome_metrics or {},
    )
    action_attrs = _action_to_dict(action)
    perm_graph.add_node(action.action_id, action_attrs)
    # Ensure subject nodes exist
    if not graph.node_exists(req.user_id):
        graph.add_node(req.user_id, {})
    # Link action to the owning user
    graph.add_edge(
        action.action_id,
        req.user_id,
        "OWNED_BY",
        {"permission_level": "editor"},
        schema_version=EDGE_VERSION,
    )
    perm_graph.rebuild_index()
    if req.group_id:
        if not graph.node_exists(req.group_id):
            graph.add_node(req.group_id, {})
        try:
            perm_graph.add_edge(
                action.action_id,
                req.group_id,
                "SHARED_WITH",
                {"permission_level": "viewer"},
            )
        except AccessDeniedError:
            raise HTTPException(
                status_code=403,
                detail="Editor permission required for target group",
            )
    perm_graph.rebuild_index()
    perm_graph.add_edge(analysis_id, action.action_id, "CONSIDERS")
    return action_attrs


@router.get("/{analysis_id}")
def get_decision(
    analysis_id: str,
    user_id: str = Query(...),
    group_id: str | None = Query(None),
    _: str = Depends(deps.get_current_role),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> dict[str, Any]:
    if group_id:
        ensure_group_member(graph, user_id, group_id)
    perm_graph = PermissionsGraphAdapter(
        graph, user_id=user_id, group_id=group_id
    )
    attrs = perm_graph.get_node(analysis_id)
    if attrs is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    analysis = {"analysis_id": analysis_id, **attrs}
    action_ids = perm_graph.find_connected_nodes(analysis_id, edge_label="CONSIDERS")
    actions = []
    for aid in action_ids:
        a_attrs = perm_graph.get_node(aid)
        if a_attrs:
            actions.append({"action_id": aid, **a_attrs})
    return {"analysis": analysis, "actions": actions}
