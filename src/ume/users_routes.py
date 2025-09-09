from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import api_deps as deps
from .graph_adapter import IGraphAdapter
from .models import create_user, create_user_group
from .permissions_adapter import PermissionsGraphAdapter
from .utils import ensure_group_member

router = APIRouter(prefix="/v1")


class UserCreateRequest(BaseModel):
    name: str
    email: str | None = None


class UserResponse(BaseModel):
    id: str
    name: str
    email: str | None = None
    schema_version: str


class UserGroupCreateRequest(BaseModel):
    name: str
    members: List[str] | None = None


class UserGroupResponse(BaseModel):
    id: str
    name: str
    members: List[str]
    schema_version: str


class OwnedByRequest(BaseModel):
    node_id: str
    owner_id: str
    permission_level: str = "editor"


class GroupMemberRequest(BaseModel):
    user_id: str


@router.post("/users", response_model=UserResponse)
def create_user_node(
    req: UserCreateRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: str = Depends(deps.get_current_role),
) -> UserResponse:
    user = create_user(req.name, email=req.email)
    attrs = {
        "type": "User",
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "created_at": int(user.created_at.timestamp()),
        "schema_version": user.schema_version,
    }
    graph.add_node(user.user_id, attrs)
    return UserResponse(
        id=user.user_id,
        name=user.name,
        email=user.email,
        schema_version=user.schema_version,
    )


@router.post("/groups", response_model=UserGroupResponse)
def create_user_group_node(
    req: UserGroupCreateRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: str = Depends(deps.get_current_role),
) -> UserGroupResponse:
    group = create_user_group(req.name, members=req.members)
    attrs = {
        "type": "UserGroup",
        "group_id": group.group_id,
        "name": group.name,
        "members": group.members,
        "schema_version": group.schema_version,
    }
    graph.add_node(group.group_id, attrs)
    return UserGroupResponse(
        id=group.group_id,
        name=group.name,
        members=group.members,
        schema_version=group.schema_version,
    )


@router.post("/owned_by")
def create_owned_by_edge(
    req: OwnedByRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: str = Depends(deps.get_current_role),
) -> dict[str, str]:
    owner_attrs = graph.get_node(req.owner_id) or {}
    if owner_attrs.get("type") == "UserGroup":
        perm_graph = PermissionsGraphAdapter(graph, group_id=req.owner_id)
    else:
        perm_graph = PermissionsGraphAdapter(graph, user_id=req.owner_id)
    perm_graph.add_edge(
        req.node_id,
        req.owner_id,
        "OWNED_BY",
        {"permission_level": req.permission_level},
    )
    return {"status": "ok"}


@router.patch("/groups/{group_id}/add_member", response_model=UserGroupResponse)
def add_group_member(
    group_id: str,
    req: GroupMemberRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: str = Depends(deps.get_current_role),
) -> UserGroupResponse:
    group_attrs = graph.get_node(group_id)
    if not group_attrs or group_attrs.get("type") != "UserGroup":
        raise HTTPException(status_code=404, detail="Group not found")
    ensure_group_member(graph, req.user_id, group_id, should_exist=False)
    members = list(group_attrs.get("members", []))
    members.append(req.user_id)
    graph.update_node(group_id, {"members": members})
    name: str = group_attrs["name"]
    schema_version: str = group_attrs["schema_version"]
    return UserGroupResponse(
        id=group_id,
        name=name,
        members=members,
        schema_version=schema_version,
    )


@router.patch("/groups/{group_id}/remove_member", response_model=UserGroupResponse)
def remove_group_member(
    group_id: str,
    req: GroupMemberRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: str = Depends(deps.get_current_role),
) -> UserGroupResponse:
    group_attrs = graph.get_node(group_id)
    if not group_attrs or group_attrs.get("type") != "UserGroup":
        raise HTTPException(status_code=404, detail="Group not found")
    ensure_group_member(graph, req.user_id, group_id)
    members = [mid for mid in group_attrs.get("members", []) if mid != req.user_id]
    graph.update_node(group_id, {"members": members})
    name: str = group_attrs["name"]
    schema_version: str = group_attrs["schema_version"]
    return UserGroupResponse(
        id=group_id,
        name=name,
        members=members,
        schema_version=schema_version,
    )
