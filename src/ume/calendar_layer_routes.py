from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, cast

from . import api_deps as deps
from .graph_adapter import IGraphAdapter
from .permissions_adapter import PermissionsGraphAdapter
from .rbac_adapter import AccessDeniedError
from .models import create_calendar_layer
from .utils import ensure_group_member

EDGE_VERSION = "3.0.0"

router = APIRouter(prefix="/v1/calendar")


class CalendarLayerCreateRequest(BaseModel):
    layer_name: str
    color: str
    layer_id: str | None = None
    user_id: str
    group_id: str | None = None


class CalendarLayerResponse(BaseModel):
    layer_id: str
    layer_name: str
    color: str
    schema_version: str


@router.post("/layers", response_model=CalendarLayerResponse)
def create_layer(
    req: CalendarLayerCreateRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: str = Depends(deps.get_current_role),
) -> CalendarLayerResponse:
    layer = create_calendar_layer(
        req.layer_name, req.color, layer_id=req.layer_id
    )
    attrs = {
        "type": "CalendarLayer",
        "layer_name": layer.layer_name,
        "color": layer.color,
        "schema_version": layer.schema_version,
    }
    graph.add_node(layer.layer_id, attrs)
    graph.add_edge(
        layer.layer_id,
        req.user_id,
        "OWNED_BY",
        {"permission_level": "editor"},
        schema_version=EDGE_VERSION,
    )
    if req.group_id:
        if not graph.node_exists(req.group_id):
            raise HTTPException(status_code=404, detail="Group not found")
        is_member = any(
            s == req.group_id
            and t == req.user_id
            and lbl == "OWNED_BY"
            and isinstance(attrs, dict)
            and attrs.get("permission_level") == "editor"
            for s, t, lbl, attrs in graph.get_all_edges()
        )
        if not is_member:
            raise HTTPException(status_code=403, detail="User not in group")
        perm_graph = PermissionsGraphAdapter(graph, user_id=req.user_id)
        try:
            perm_graph.add_edge(
                layer.layer_id,
                req.group_id,
                "SHARED_WITH",
                {"permission_level": "viewer"},
            )
        except AccessDeniedError as exc:  # pragma: no cover - ensure 403 response
            raise HTTPException(status_code=403, detail=str(exc))
    return CalendarLayerResponse(
        layer_id=layer.layer_id,
        layer_name=layer.layer_name,
       color=layer.color,
       schema_version=layer.schema_version,
    )


@router.get("/layers", response_model=List[CalendarLayerResponse])
def list_layers(
    user_id: str = Query(...),
    group_id: str | None = Query(None),
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: str = Depends(deps.get_current_role),
) -> List[CalendarLayerResponse]:
    if group_id is not None:
        ensure_group_member(graph, user_id, group_id)
    perm_graph = PermissionsGraphAdapter(
        graph, user_id=user_id, group_id=group_id
    )

    layer_ids = set(perm_graph.get_nodes_by_user(user_id))
    if group_id is not None:
        layer_ids |= set(perm_graph.get_nodes_shared_with(group_id))
    layers: List[CalendarLayerResponse] = []
    for lid in layer_ids:
        attrs = graph.get_node(lid)
        if not attrs or attrs.get("type") != "CalendarLayer":
            continue
        layers.append(
            CalendarLayerResponse(
                layer_id=lid,
                layer_name=cast(str, attrs.get("layer_name")),
                color=cast(str, attrs.get("color")),
                schema_version=cast(str, attrs.get("schema_version")),

            )
        )
    return layers
