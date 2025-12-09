from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from . import api_deps as deps
from .graph_adapter import IGraphAdapter
from .graph_schema import get_default_edge_version
from .permissions_adapter import PermissionsGraphAdapter
from .rbac_adapter import AccessDeniedError
from .utils import ensure_group_member
from .models import (
    DecisionAnalysis,
    ProposedAction,
    create_decision_analysis,
    create_proposed_action,
    create_user,
    create_user_group,
)

VALID_GROUP_PERMISSION_LEVELS = {"viewer", "editor"}

EDGE_VERSION = get_default_edge_version("OWNED_BY")

router = APIRouter(prefix="/v1/decisions")


class DecisionCreateRequest(BaseModel):
    query: str
    user_id: str
    group_id: str | None = None
    group_permission_level: str | None = None


class ActionCreateRequest(BaseModel):
    description: str
    rank: int = 0
    is_optimal: bool = False
    outcome_metrics: dict[str, Any] | None = None
    user_id: str
    group_id: str | None = None
    group_permission_level: str | None = None


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


def _user_node_defaults(user_id: str) -> dict[str, Any]:
    user = create_user(user_id, user_id=user_id)
    return {
        "type": "User",
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "created_at": int(user.created_at.timestamp()),
        "schema_version": user.schema_version,
    }


def _ensure_user_node(graph: IGraphAdapter, user_id: str) -> None:
    defaults = _user_node_defaults(user_id)
    attrs = graph.get_node(user_id)
    if attrs is None:
        graph.add_node(user_id, defaults)
        return
    update_attrs: dict[str, Any] = {}
    if attrs.get("type") != "User":
        update_attrs["type"] = "User"
    for field in ("user_id", "name", "email", "created_at"):
        if attrs.get(field) is None:
            update_attrs[field] = defaults[field]
    if not attrs.get("schema_version"):
        update_attrs["schema_version"] = defaults["schema_version"]
    if update_attrs:
        graph.update_node(user_id, update_attrs)


def _group_node_defaults(group_id: str) -> dict[str, Any]:
    group = create_user_group(group_id, group_id=group_id)
    return {
        "type": "UserGroup",
        "group_id": group.group_id,
        "name": group.name,
        "members": list(group.members),
        "schema_version": group.schema_version,
    }


def _ensure_group_node(graph: IGraphAdapter, group_id: str) -> None:
    defaults = _group_node_defaults(group_id)
    attrs = graph.get_node(group_id)
    if attrs is None:
        graph.add_node(group_id, defaults)
        return
    update_attrs: dict[str, Any] = {}
    if attrs.get("type") != "UserGroup":
        update_attrs["type"] = "UserGroup"
    if not attrs.get("group_id"):
        update_attrs["group_id"] = defaults["group_id"]
    if not attrs.get("name"):
        update_attrs["name"] = defaults["name"]
    if "members" not in attrs:
        update_attrs["members"] = defaults["members"]
    if not attrs.get("schema_version"):
        update_attrs["schema_version"] = defaults["schema_version"]
    if update_attrs:
        graph.update_node(group_id, update_attrs)


@router.post("")
def create_decision(
    req: DecisionCreateRequest,
    _: str = Depends(deps.get_current_role),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> dict[str, Any]:
    if req.group_id:
        ensure_group_member(graph, req.user_id, req.group_id)
        _ensure_group_node(graph, req.group_id)
        group_permission_level = req.group_permission_level or "editor"
        if group_permission_level not in VALID_GROUP_PERMISSION_LEVELS:
            raise HTTPException(status_code=400, detail="Invalid group_permission_level")
    perm_graph = PermissionsGraphAdapter(
        graph, user_id=req.user_id, group_id=req.group_id
    )
    analysis = create_decision_analysis(req.query)
    attrs = _analysis_to_dict(analysis)
    perm_graph.add_node(analysis.analysis_id, attrs)
    # Ensure subject nodes exist
    _ensure_user_node(graph, req.user_id)
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
        perm_graph.add_edge(
            analysis.analysis_id,
            req.group_id,
            "SHARED_WITH",
            {"permission_level": group_permission_level},
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
        _ensure_group_node(graph, req.group_id)
        group_permission_level = req.group_permission_level or "viewer"
        if group_permission_level not in VALID_GROUP_PERMISSION_LEVELS:
            raise HTTPException(status_code=400, detail="Invalid group_permission_level")
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
    _ensure_user_node(graph, req.user_id)
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
        try:
            perm_graph.add_edge(
                action.action_id,
                req.group_id,
                "SHARED_WITH",
                {"permission_level": group_permission_level},
            )
        except AccessDeniedError:
            raise HTTPException(
                status_code=403,
                detail="Editor permission required for target group",
            )
    perm_graph.rebuild_index()
    try:
        perm_graph.add_edge(analysis_id, action.action_id, "CONSIDERS")
    except AccessDeniedError:
        perm_graph.redact_node(action.action_id)
        perm_graph.rebuild_index()
        raise HTTPException(status_code=403)
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
