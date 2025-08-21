from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import api_deps as deps
from .graph_adapter import IGraphAdapter
from .permissions_adapter import PermissionsGraphAdapter
from .rbac_adapter import AccessDeniedError
from .models import create_calendar_layer

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
        perm_graph = PermissionsGraphAdapter(graph, user_id=req.user_id)
        try:
            perm_graph._require_editor(req.group_id)
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
