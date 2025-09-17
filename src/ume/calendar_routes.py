from __future__ import annotations

from contextlib import suppress
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from . import api_deps as deps
from .graph_adapter import IGraphAdapter
from .permissions_adapter import PermissionsGraphAdapter
from .rbac_adapter import AccessDeniedError
from .utils import ensure_group_member
from .models import (
    CalendarEventStatus,
    CalendarEventVisibility,
    create_calendar_event,
    create_user,
)

EDGE_VERSION = "3.0.0"

router = APIRouter(prefix="/v1/calendar")


def _ensure_user_node(graph: IGraphAdapter, user_id: str) -> None:
    """Create a full user node if one does not already exist."""
    if graph.node_exists(user_id):
        return
    user = create_user(user_id, user_id=user_id)
    attrs = {
        "type": "User",
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "created_at": int(user.created_at.timestamp()),
        "schema_version": user.schema_version,
    }
    graph.add_node(user.user_id, attrs)


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
    event_id: str
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
    if req.end_time is not None and req.end_time <= req.start_time:
        raise HTTPException(
            status_code=400, detail="end_time must be after start_time"

        )
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
    _ensure_user_node(graph, req.user_id)
    if req.group_id:
        ensure_group_member(graph, req.user_id, req.group_id)
        if event.visibility != CalendarEventVisibility.PUBLIC_TO_GROUP:
            raise HTTPException(
                status_code=400,
                detail="Group events must have visibility public_to_group",
            )
    perm_graph = PermissionsGraphAdapter(graph, user_id=req.user_id)

    try:
        try:
            perm_graph.add_edge(
                event.event_id, req.user_id, "OWNED_BY", {"permission_level": "editor"}
            )
        except AccessDeniedError:
            graph.add_edge(
                event.event_id,
                req.user_id,
                "OWNED_BY",
                {"permission_level": "editor"},
                schema_version=EDGE_VERSION,
            )
            perm_graph.rebuild_index()

        for uid in invitee_ids:

            try:
                perm_graph.add_edge(event.event_id, uid, "INVITES")
                perm_graph.add_edge(
                    event.event_id, uid, "SHARED_WITH", {"permission_level": "viewer"}
                )
            except AccessDeniedError as exc:
                raise HTTPException(status_code=403, detail=str(exc))

        if req.group_id:
            try:
                perm_graph.add_edge(
                    event.event_id,
                    req.group_id,
                    "SHARED_WITH",
                    {"permission_level": "viewer"},
                )
            except AccessDeniedError as exc:
                raise HTTPException(status_code=403, detail=str(exc))

        for lid in layer_ids:

            try:
                perm_graph.add_edge(event.event_id, lid, "TAGGED_AS")
            except AccessDeniedError as exc:
                raise HTTPException(status_code=403, detail=str(exc))
    except Exception:
        graph.redact_node(event.event_id)

        raise
    return CalendarEventResponse(
        event_id=event.event_id,
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
        ensure_group_member(graph, user_id, group_id)
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
        if (
            group_id is not None
            and attrs.get("visibility")
            != CalendarEventVisibility.PUBLIC_TO_GROUP.value
        ):
            continue
        start_ts = attrs.get("start_time")
        if since is not None and (start_ts is None or start_ts <= since):
            continue
        events.append(
            CalendarEventResponse(
                event_id=eid,
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
