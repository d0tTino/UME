from __future__ import annotations

from contextlib import suppress
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from . import api_deps as deps
from .graph_adapter import IGraphAdapter
from .permissions_adapter import PermissionsGraphAdapter
from .rbac_adapter import AccessDeniedError
from .processing import ProcessingError
from .schema_manager import DEFAULT_SCHEMA_MANAGER
from .graph_mutations import add_edge_with_schema_validation, add_node_with_schema_validation
from .schema_validation import validate_node_attributes
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


router = APIRouter(prefix="/v1/decisions")


def _add_node_or_http(
    graph: IGraphAdapter,
    node_id: str,
    attrs: dict[str, Any],
    schema,
) -> dict[str, Any]:
    try:
        return add_node_with_schema_validation(graph, node_id, attrs, schema=schema)
    except ProcessingError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid node payload for '{node_id}': {exc}",
        )


def _validate_node_or_http(attrs: dict[str, Any], schema) -> str:
    try:
        return validate_node_attributes(attrs, schema=schema)
    except ProcessingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _add_edge_or_http(
    graph: IGraphAdapter,
    source_node_id: str,
    target_node_id: str,
    label: str,
    attrs: dict[str, Any] | None,
    schema,
    schema_version: str | None = None,
) -> str:
    try:
        return add_edge_with_schema_validation(
            graph,
            source_node_id,
            target_node_id,
            label,
            attrs,
            schema=schema,
            schema_version=schema_version,
        )
    except ProcessingError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid edge '{label}' from '{source_node_id}' to "
                f"'{target_node_id}': {exc}"
            ),
        )



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


def _analysis_to_dict(analysis: DecisionAnalysis, schema) -> dict[str, Any]:
    return {
        "type": "DecisionAnalysis",
        "analysis_id": analysis.analysis_id,
        "query": analysis.query,
        "created_at": int(analysis.created_at.timestamp()),
        "schema_version": schema.node_types["DecisionAnalysis"].version,
    }


def _action_to_dict(action: ProposedAction, schema) -> dict[str, Any]:
    return {
        "type": "ProposedAction",
        "action_id": action.action_id,
        "description": action.description,
        "rank": action.rank,
        "is_optimal": action.is_optimal,
        "outcome_metrics": action.outcome_metrics,
        "schema_version": schema.node_types["ProposedAction"].version,
    }


def _user_node_defaults(user_id: str, schema) -> dict[str, Any]:
    user = create_user(user_id, user_id=user_id)
    return {
        "type": "User",
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "created_at": int(user.created_at.timestamp()),
        "schema_version": schema.node_types["User"].version,
    }


def _ensure_user_node(graph: IGraphAdapter, user_id: str, schema) -> None:
    defaults = _user_node_defaults(user_id, schema)
    attrs = graph.get_node(user_id)
    if attrs is None:
        _add_node_or_http(graph, user_id, defaults, schema)
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
        _validate_node_or_http({**attrs, **update_attrs}, schema)
        graph.update_node(user_id, update_attrs)


def _group_node_defaults(group_id: str, schema) -> dict[str, Any]:
    group = create_user_group(group_id, group_id=group_id)
    return {
        "type": "UserGroup",
        "group_id": group.group_id,
        "name": group.name,
        "members": list(group.members),
        "schema_version": schema.node_types["UserGroup"].version,
    }


def _ensure_group_node(graph: IGraphAdapter, group_id: str, schema) -> None:
    defaults = _group_node_defaults(group_id, schema)
    attrs = graph.get_node(group_id)
    if attrs is None:
        _add_node_or_http(graph, group_id, defaults, schema)
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
        _validate_node_or_http({**attrs, **update_attrs}, schema)
        graph.update_node(group_id, update_attrs)


@router.post("")
def create_decision(
    req: DecisionCreateRequest,
    _: str = Depends(deps.get_current_role),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> dict[str, Any]:
    schema = DEFAULT_SCHEMA_MANAGER.get_schema()
    if req.group_id:
        ensure_group_member(graph, req.user_id, req.group_id)
        _ensure_group_node(graph, req.group_id, schema)
        group_permission_level = req.group_permission_level or "editor"
        if group_permission_level not in VALID_GROUP_PERMISSION_LEVELS:
            raise HTTPException(status_code=400, detail="Invalid group_permission_level")
    perm_graph = PermissionsGraphAdapter(
        graph, user_id=req.user_id, group_id=req.group_id
    )
    try:
        analysis = create_decision_analysis(req.query)
        attrs = _analysis_to_dict(analysis, schema)
        attrs = _add_node_or_http(perm_graph, analysis.analysis_id, attrs, schema)
        # Ensure subject nodes exist
        _ensure_user_node(graph, req.user_id, schema)
        # Link analysis to the owning user
        with perm_graph.bootstrap_owner(analysis.analysis_id):
            _add_edge_or_http(
                perm_graph,
                analysis.analysis_id,
                req.user_id,
                "OWNED_BY",
                {"permission_level": "editor"},
                schema,
            )
        if req.group_id:
            _add_edge_or_http(
                perm_graph,
                analysis.analysis_id,
                req.group_id,
                "SHARED_WITH",
                {"permission_level": group_permission_level},
                schema,
            )
    except AccessDeniedError as exc:
        status = 400 if "bootstrapped" in str(exc) else 403
        raise HTTPException(status_code=status, detail=str(exc))
    except ProcessingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return attrs


@router.post("/{analysis_id}/actions")
def add_action(
    analysis_id: str,
    req: ActionCreateRequest,
    _: str = Depends(deps.get_current_role),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> dict[str, Any]:
    schema = DEFAULT_SCHEMA_MANAGER.get_schema()
    if req.group_id:
        ensure_group_member(graph, req.user_id, req.group_id)
        _ensure_group_node(graph, req.group_id, schema)
        group_permission_level = req.group_permission_level or "viewer"
        if group_permission_level not in VALID_GROUP_PERMISSION_LEVELS:
            raise HTTPException(status_code=400, detail="Invalid group_permission_level")
    perm_graph = PermissionsGraphAdapter(
        graph, user_id=req.user_id, group_id=req.group_id
    )
    if not perm_graph.node_exists(analysis_id):
        raise HTTPException(status_code=404, detail="Analysis not found")
    created_action = False
    try:
        action = create_proposed_action(
            req.description,
            rank=req.rank,
            is_optimal=req.is_optimal,
            outcome_metrics=req.outcome_metrics or {},
        )
        action_attrs = _action_to_dict(action, schema)
        action_attrs = _add_node_or_http(perm_graph, action.action_id, action_attrs, schema)
        created_action = True
        # Ensure subject nodes exist
        _ensure_user_node(graph, req.user_id, schema)
        # Link action to the owning user
        with perm_graph.bootstrap_owner(action.action_id):
            _add_edge_or_http(
                perm_graph,
                action.action_id,
                req.user_id,
                "OWNED_BY",
                {"permission_level": "editor"},
                schema,
            )
        perm_graph.rebuild_index()
        if req.group_id:
            try:
                _add_edge_or_http(
                    perm_graph,
                    action.action_id,
                    req.group_id,
                    "SHARED_WITH",
                    {"permission_level": group_permission_level},
                    schema,
                )
            except AccessDeniedError as exc:
                raise AccessDeniedError("Editor permission required for target group") from exc
        perm_graph.rebuild_index()
        _add_edge_or_http(
            perm_graph,
            analysis_id,
            action.action_id,
            "CONSIDERS",
            {},
            schema,
        )
    except AccessDeniedError as exc:
        if created_action:
            with suppress(ProcessingError, AccessDeniedError):
                perm_graph.redact_node(action.action_id)
            perm_graph.rebuild_index()
        status = 400 if "bootstrapped" in str(exc) else 403
        raise HTTPException(status_code=status, detail=str(exc))
    except ProcessingError as exc:
        if created_action:
            with suppress(ProcessingError, AccessDeniedError):
                perm_graph.redact_node(action.action_id)
            perm_graph.rebuild_index()
        raise HTTPException(status_code=400, detail=str(exc))
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
