from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from . import api_deps as deps
from .graph_adapter import IGraphAdapter
from .permissions_adapter import PermissionsGraphAdapter
from .models import create_calendar_event

router = APIRouter(prefix="/v1/calendar")


class CalendarEventCreateRequest(BaseModel):
    title: str
    start: datetime
    end: datetime | None = None
    description: str | None = None
    is_all_day: bool = False
    location: str | None = None
    status: str | None = None
    rrule: str | None = None
    visibility: str | None = None
    user_id: str
    invitee_ids: List[str] | None = None
    layer_ids: List[str] | None = None


class CalendarEventResponse(BaseModel):
    id: str
    title: str
    start: int
    end: int | None = None
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
        req.start,
        req.end,
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
        "start": int(event.start.timestamp()),
        "end": int(event.end.timestamp()) if event.end else None,
        "description": event.description,
        "is_all_day": event.is_all_day,
        "location": event.location,
        "status": event.status,
        "rrule": event.rrule,
        "visibility": event.visibility,
    }
    graph.add_node(event.id, attrs)
    graph.add_edge(event.id, req.user_id, "OWNED_BY")
    graph.add_edge(
        event.id,
        req.user_id,
        "HAS_PERMISSION",
        {"permission_level": "editor"},
    )
    for uid in req.invitee_ids or []:
        graph.add_edge(event.id, uid, "INVITES")
        graph.add_edge(
            event.id, uid, "HAS_PERMISSION", {"permission_level": "viewer"}
        )
    for lid in req.layer_ids or []:
        graph.add_edge(event.id, lid, "TAGGED_AS")
    return CalendarEventResponse(
        id=event.id,
        title=event.title,
        start=attrs["start"],
        end=attrs["end"],
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
    layer_id: str | None = Query(None),
    since: int | None = Query(None, ge=0),
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: str = Depends(deps.get_current_role),
) -> List[CalendarEventResponse]:
    perm_graph = PermissionsGraphAdapter(graph, user_id=user_id)
    event_ids = set(perm_graph.get_nodes_by_user(user_id))
    if layer_id is not None:
        layer_events = {
            src
            for src, tgt, lbl, _ in graph.get_all_edges()
            if lbl == "TAGGED_AS" and tgt == layer_id
        }
        event_ids &= layer_events
    events: List[CalendarEventResponse] = []
    for eid in event_ids:
        attrs = graph.get_node(eid)
        if not attrs:
            continue
        start_ts = attrs.get("start")
        if since is not None and (start_ts is None or start_ts < since):
            continue
        events.append(
            CalendarEventResponse(
                id=eid,
                title=attrs.get("title", ""),
                start=start_ts,
                end=attrs.get("end"),
                description=attrs.get("description"),
                is_all_day=attrs.get("is_all_day", False),
                location=attrs.get("location"),
                status=attrs.get("status"),
                rrule=attrs.get("rrule"),
                visibility=attrs.get("visibility"),
            )
        )
    return events
