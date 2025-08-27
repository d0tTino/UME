from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from . import api_deps as deps
from .graph_adapter import IGraphAdapter
from .permissions_adapter import PermissionsGraphAdapter
from .rbac_adapter import AccessDeniedError
from .models import (
    CalendarEventStatus,
    CalendarEventVisibility,
    create_calendar_event,
)

EDGE_VERSION = "3.0.0"

router = APIRouter(prefix="/v1/calendar")


class CalendarEventCreateRequest(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime | None = None
    description: str | None = None
    is_all_day: bool = False
    location: str | None = None
    status: CalendarEventStatus | None = None
    rrule: str | None = None
    visibility: CalendarEventVisibility | None = None
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
    status: CalendarEventStatus | None = None
    rrule: str | None = None
    visibility: CalendarEventVisibility | None = None
    schema_version: str


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
        "status": event.status.value if event.status else None,
        "rrule": event.rrule,
        "visibility": event.visibility.value if event.visibility else None,
        "schema_version": event.schema_version,
    }
    if not graph.node_exists(req.user_id):
        graph.add_node(req.user_id, {"type": "User"})
    if req.group_id:
        group_attrs = graph.get_node(req.group_id)
        members = group_attrs.get("members", []) if group_attrs else []
        if req.user_id not in members:
            raise HTTPException(status_code=403, detail="User not in group")
    graph.add_node(event.id, attrs)
    perm_graph = PermissionsGraphAdapter(graph, user_id=req.user_id)
    try:
        perm_graph.add_edge(
            event.id, req.user_id, "OWNED_BY", {"permission_level": "editor"}
        )
    except AccessDeniedError:
        graph.add_edge(
            event.id,
            req.user_id,
            "OWNED_BY",
            {"permission_level": "editor"},
            schema_version=EDGE_VERSION,
        )
        perm_graph.rebuild_index()
    for uid in req.invitee_ids or []:
        if not graph.node_exists(uid):
            graph.add_node(uid, {"type": "User"})
        try:
            perm_graph.add_edge(event.id, uid, "INVITES")
            perm_graph.add_edge(
                event.id, uid, "SHARED_WITH", {"permission_level": "viewer"}
            )
        except AccessDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
    if req.group_id:
        try:
            perm_graph.add_edge(
                event.id,
                req.group_id,
                "SHARED_WITH",
                {"permission_level": "viewer"},
            )
        except AccessDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
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
        try:
            perm_graph.add_edge(event.id, lid, "TAGGED_AS")
        except AccessDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
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
        schema_version=event.schema_version,
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
    if group_id is not None:
        group_attrs = graph.get_node(group_id)
        members = group_attrs.get("members", []) if group_attrs else []
        if user_id not in members:
            raise HTTPException(status_code=403, detail="User not in group")
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
        if not attrs or attrs.get("type") != "CalendarEvent":
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
                schema_version=attrs.get("schema_version", ""),
            )
        )
    return events
