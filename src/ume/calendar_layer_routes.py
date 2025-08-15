from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from . import api_deps as deps
from .graph_adapter import IGraphAdapter
from .models import create_calendar_layer

router = APIRouter(prefix="/v1/calendar")


class CalendarLayerCreateRequest(BaseModel):
    layer_name: str
    color: str
    layer_id: str | None = None


class CalendarLayerResponse(BaseModel):
    layer_id: str
    layer_name: str
    color: str


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
    }
    graph.add_node(layer.layer_id, attrs)
    return CalendarLayerResponse(
        layer_id=layer.layer_id,
        layer_name=layer.layer_name,
        color=layer.color,
    )
