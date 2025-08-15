from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from . import api_deps as deps
from .graph_adapter import IGraphAdapter
from .models import create_user, create_user_group

router = APIRouter(prefix="/v1")


class UserCreateRequest(BaseModel):
    name: str
    email: str | None = None


class UserResponse(BaseModel):
    id: str
    name: str
    email: str | None = None


class UserGroupCreateRequest(BaseModel):
    name: str
    members: List[str] | None = None


class UserGroupResponse(BaseModel):
    id: str
    name: str
    members: List[str]


class OwnedByRequest(BaseModel):
    node_id: str
    owner_id: str
    permission_level: str = "editor"


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
    }
    graph.add_node(user.user_id, attrs)
    return UserResponse(id=user.user_id, name=user.name, email=user.email)


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
    }
    graph.add_node(group.group_id, attrs)
    return UserGroupResponse(id=group.group_id, name=group.name, members=group.members)


@router.post("/owned_by")
def create_owned_by_edge(
    req: OwnedByRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: str = Depends(deps.get_current_role),
) -> dict[str, str]:
    graph.add_edge(
        req.node_id,
        req.owner_id,
        "OWNED_BY",
        {"permission_level": req.permission_level},
    )
    return {"status": "ok"}
