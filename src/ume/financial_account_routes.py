from __future__ import annotations

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import cast

from . import api_deps as deps
from .graph_adapter import IGraphAdapter
from .permissions_adapter import PermissionsGraphAdapter
from .models import create_financial_account

EDGE_VERSION = "3.0.0"

router = APIRouter(prefix="/v1/accounts")


class FinancialAccountCreateRequest(BaseModel):
    account_type: str
    institution: str
    balance: float
    currency: str = "USD"
    user_id: str
    group_id: str | None = None


class FinancialAccountResponse(BaseModel):
    id: str
    account_type: str
    institution: str
    balance: float
    currency: str
    schema_version: str


@router.post("", response_model=FinancialAccountResponse)
def create_account(
    req: FinancialAccountCreateRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: str = Depends(deps.get_current_role),
) -> FinancialAccountResponse:
    if not graph.node_exists(req.user_id):
        graph.add_node(req.user_id, {})
    if req.group_id:
        group_attrs = graph.get_node(req.group_id)
        if group_attrs is None or group_attrs.get("type") != "UserGroup":
            raise HTTPException(status_code=404, detail="Group not found")
        members = cast(list[str], group_attrs.get("members", []))
        if req.user_id not in members:
            raise HTTPException(status_code=403, detail="User not in group")
    account = create_financial_account(
        req.account_type,
        req.institution,
        req.balance,
        currency=req.currency,
    )
    attrs = {
        "type": "FinancialAccount",
        "account_type": account.account_type,
        "institution": account.institution,
        "balance": account.balance,
        "currency": account.currency,
        "schema_version": account.schema_version,
    }
    graph.add_node(account.account_id, attrs)
    graph.add_edge(
        account.account_id,
        req.user_id,
        "OWNED_BY",
        {"permission_level": "editor"},
        schema_version=EDGE_VERSION,
    )
    perm_graph = PermissionsGraphAdapter(graph, user_id=req.user_id)
    if req.group_id:
        perm_graph.add_edge(
            account.account_id,
            req.group_id,
            "SHARED_WITH",
            {"permission_level": "viewer"},
        )

    return FinancialAccountResponse(
        id=account.account_id,
        account_type=account.account_type,
        institution=account.institution,
        balance=account.balance,
        currency=account.currency,
        schema_version=account.schema_version,
    )


@router.get("/{account_id}", response_model=FinancialAccountResponse)
def get_account(
    account_id: str,
    user_id: str = Query(...),
    group_id: str | None = Query(None),
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: str = Depends(deps.get_current_role),
) -> FinancialAccountResponse:
    if group_id:
        group_attrs = graph.get_node(group_id)
        if group_attrs is None or group_attrs.get("type") != "UserGroup":
            raise HTTPException(status_code=404, detail="Group not found")
        members = cast(list[str], group_attrs.get("members", []))
        if user_id not in members:
            raise HTTPException(status_code=403, detail="User not in group")
    perm_graph = PermissionsGraphAdapter(
        graph, user_id=user_id, group_id=group_id
    )
    attrs = perm_graph.get_node(account_id)
    if attrs is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return FinancialAccountResponse(
        id=account_id,
        account_type=cast(str, attrs.get("account_type")),
        institution=cast(str, attrs.get("institution")),
        balance=cast(float, attrs.get("balance")),
        currency=cast(str, attrs.get("currency")),
        schema_version=cast(str, attrs.get("schema_version")),
    )
