from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from . import api_deps as deps
from .graph_adapter import IGraphAdapter
from .permissions_adapter import PermissionsGraphAdapter
from .models import create_calendar_event

router = APIRouter(prefix="/v1/calendar")


class CalendarEventCreateRequest(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime | None = None
    description: str | None = None
    is_all_day: bool = False
    location: str | None = None
    status: str | None = None
    rrule: str | None = None
    visibility: str | None = None
    user_id: str
    group_id: str | None = None
    invitee_ids: List[str] | None = None
    layer_ids: List[str] | None = None


class CalendarEventResponse(BaseModel):
    id: str
    title: str
    start_time: int
    end_time: int | None = None
    description: str | None = None
    is_all_day: bool
    location: str | None = None
    status: str | None = None
    rrule: str | None = None
    visibility: str | None = None


@router.post("/events", response_model=CalendarEventResponse)
def create_event(
    req: CalendarEventCreateRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: str = Depends(deps.get_current_role),
) -> CalendarEventResponse:
    event = create_calendar_event(
        req.title,
        req.start_time,
        req.end_time,
        description=req.description,
        is_all_day=req.is_all_day,
        location=req.location,
        status=req.status,
        rrule=req.rrule,
        visibility=req.visibility,
    )
    attrs = {
        "type": "CalendarEvent",
        "title": event.title,
        "start_time": int(event.start_time.timestamp()),
        "end_time": int(event.end_time.timestamp()) if event.end_time else None,
        "description": event.description,
        "is_all_day": event.is_all_day,
        "location": event.location,
        "status": event.status,
        "rrule": event.rrule,
        "visibility": event.visibility,
    }
    if not graph.node_exists(req.user_id):
        graph.add_node(req.user_id, {"type": "User"})
    if req.group_id and not graph.node_exists(req.group_id):
        graph.add_node(req.group_id, {"type": "UserGroup"})
    graph.add_node(event.id, attrs)
    graph.add_edge(
        event.id, req.user_id, "OWNED_BY", {"permission_level": "editor"}
    )
    perm_graph = PermissionsGraphAdapter(graph, user_id=req.user_id)
    for uid in req.invitee_ids or []:
        if not graph.node_exists(uid):
            graph.add_node(uid, {"type": "User"})
        graph.add_edge(event.id, uid, "INVITES")
        graph.add_edge(
            event.id, uid, "SHARED_WITH", {"permission_level": "viewer"}
        )
    if req.group_id:
        graph.add_edge(
            event.id,
            req.group_id,
            "SHARED_WITH",
            {"permission_level": "viewer"},
        )
    for lid in req.layer_ids or []:
        layer_attrs = graph.get_node(lid)
        if not layer_attrs or layer_attrs.get("type") != "CalendarLayer":
            raise HTTPException(
                status_code=400, detail=f"Invalid layer_id: {lid}"
            )
        if not perm_graph.node_exists(lid):
            raise HTTPException(
                status_code=403, detail=f"No access to layer: {lid}"
            )
        graph.add_edge(event.id, lid, "TAGGED_AS")
    return CalendarEventResponse(
        id=event.id,
        title=event.title,
        start_time=attrs["start_time"],
        end_time=attrs["end_time"],
        description=event.description,
        is_all_day=event.is_all_day,
        location=event.location,
        status=event.status,
        rrule=event.rrule,
        visibility=event.visibility,
    )


@router.get("/events", response_model=List[CalendarEventResponse])
def list_events(
    user_id: str = Query(...),
    group_id: str | None = Query(None),
    layer_id: str | None = Query(None),
    since: int | None = Query(None, ge=0),
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: str = Depends(deps.get_current_role),
) -> List[CalendarEventResponse]:
    perm_graph = PermissionsGraphAdapter(
        graph, user_id=user_id, group_id=group_id
    )
    event_ids = set(perm_graph.get_nodes_by_user(user_id))
    if group_id is not None:
        event_ids |= set(perm_graph.get_nodes_shared_with(group_id))
    if layer_id is not None:
        layer_events = {
            src
            for src, tgt, lbl, _ in perm_graph.get_all_edges()
            if lbl == "TAGGED_AS" and tgt == layer_id
        }
        event_ids &= layer_events
    events: List[CalendarEventResponse] = []
    for eid in event_ids:
        attrs = graph.get_node(eid)
        if not attrs:
            continue
        start_ts = attrs.get("start_time")
        if since is not None and (start_ts is None or start_ts < since):
            continue
        events.append(
            CalendarEventResponse(
                id=eid,
                title=attrs.get("title", ""),
                start_time=start_ts,
                end_time=attrs.get("end_time"),
                description=attrs.get("description"),
                is_all_day=attrs.get("is_all_day", False),
                location=attrs.get("location"),
                status=attrs.get("status"),
                rrule=attrs.get("rrule"),
                visibility=attrs.get("visibility"),
            )
        )
    return events
