from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import api_deps as deps
from .graph_adapter import IGraphAdapter
from .models import (
    DecisionAnalysis,
    ProposedAction,
    create_decision_analysis,
    create_proposed_action,
)

router = APIRouter(prefix="/v1/decisions")


class DecisionCreateRequest(BaseModel):
    query: str


class ActionCreateRequest(BaseModel):
    description: str
    rank: int = 0
    is_optimal: bool = False
    outcome_metrics: dict[str, float] | None = None


def _analysis_to_dict(analysis: DecisionAnalysis) -> dict[str, Any]:
    return {
        "analysis_id": analysis.analysis_id,
        "query": analysis.query,
        "created_at": int(analysis.created_at.timestamp()),
    }


def _action_to_dict(action: ProposedAction) -> dict[str, Any]:
    return {
        "action_id": action.action_id,
        "description": action.description,
        "rank": action.rank,
        "is_optimal": action.is_optimal,
        "outcome_metrics": action.outcome_metrics,
    }


@router.post("")
def create_decision(
    req: DecisionCreateRequest,
    _: str = Depends(deps.get_current_role),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> dict[str, Any]:
    analysis = create_decision_analysis(req.query)
    attrs = _analysis_to_dict(analysis)
    graph.add_node(analysis.analysis_id, attrs)
    return attrs


@router.post("/{analysis_id}/actions")
def add_action(
    analysis_id: str,
    req: ActionCreateRequest,
    _: str = Depends(deps.get_current_role),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> dict[str, Any]:
    if not graph.node_exists(analysis_id):
        raise HTTPException(status_code=404, detail="Analysis not found")
    action = create_proposed_action(
        req.description,
        rank=req.rank,
        is_optimal=req.is_optimal,
        outcome_metrics=req.outcome_metrics or {},
    )
    action_attrs = _action_to_dict(action)
    graph.add_node(action.action_id, action_attrs)
    graph.add_edge(analysis_id, action.action_id, "CONSIDERS")
    return action_attrs


@router.get("/{analysis_id}")
def get_decision(
    analysis_id: str,
    _: str = Depends(deps.get_current_role),
    graph: IGraphAdapter = Depends(deps.get_graph),
) -> dict[str, Any]:
    attrs = graph.get_node(analysis_id)
    if attrs is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    analysis = {"analysis_id": analysis_id, **attrs}
    action_ids = graph.find_connected_nodes(analysis_id, edge_label="CONSIDERS")
    actions = []
    for aid in action_ids:
        a_attrs = graph.get_node(aid)
        if a_attrs:
            actions.append({"action_id": aid, **a_attrs})
    return {"analysis": analysis, "actions": actions}
