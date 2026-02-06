from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from . import api_deps as deps
from .graph_adapter import IGraphAdapter
from .permissions_adapter import PermissionsGraphAdapter
from .rbac_adapter import AccessDeniedError
from .schema_manager import DEFAULT_SCHEMA_MANAGER
from .graph_mutations import add_edge_with_schema_validation, add_node_with_schema_validation
from .models import create_financial_account, create_user
from .processing import ProcessingError
from .utils import ensure_group_member

router = APIRouter(prefix="/v1/accounts")


def _add_node_or_http(
    graph: IGraphAdapter,
    node_id: str,
    attrs: dict[str, Any],
    schema,
) -> dict[str, Any]:
    try:
        return add_node_with_schema_validation(graph, node_id, attrs, schema=schema)
    except ProcessingError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid node payload for '{node_id}': {exc}",
        )


def _add_edge_or_http(
    graph: IGraphAdapter,
    source_node_id: str,
    target_node_id: str,
    label: str,
    attrs: dict[str, Any] | None,
    schema,
    schema_version: str | None = None,
) -> str:
    try:
        return add_edge_with_schema_validation(
            graph,
            source_node_id,
            target_node_id,
            label,
            attrs,
            schema=schema,
            schema_version=schema_version,
        )
    except ProcessingError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid edge '{label}' from '{source_node_id}' to "
                f"'{target_node_id}': {exc}"
            ),
        )


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
    schema = DEFAULT_SCHEMA_MANAGER.get_schema()
    if not graph.node_exists(req.user_id):
        user = create_user(req.user_id, user_id=req.user_id)
        user_attrs = {
            "type": "User",
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
            "created_at": int(user.created_at.timestamp()),
            "schema_version": schema.node_types["User"].version,
        }
        _add_node_or_http(graph, user.user_id, user_attrs, schema)
    if req.group_id:
        group_attrs = graph.get_node(req.group_id)
        if group_attrs is None or group_attrs.get("type") != "UserGroup":
            raise HTTPException(status_code=404, detail="Group not found")
        ensure_group_member(graph, req.user_id, req.group_id)
    account = create_financial_account(
        req.account_type,
        req.institution,
        req.balance,
        currency=req.currency,
    )
    attrs = {
        "type": "FinancialAccount",
        "account_id": account.account_id,
        "account_type": account.account_type,
        "institution": account.institution,
        "balance": account.balance,
        "currency": account.currency,
        "schema_version": schema.node_types["FinancialAccount"].version,
    }
    attrs = _add_node_or_http(graph, account.account_id, attrs, schema)
    perm_graph = PermissionsGraphAdapter(graph, user_id=req.user_id)
    try:
        with perm_graph.bootstrap_owner(account.account_id):
            _add_edge_or_http(
                perm_graph,
                account.account_id,
                req.user_id,
                "OWNED_BY",
                {"permission_level": "editor"},
                schema,
            )
        if req.group_id:
            _add_edge_or_http(
                perm_graph,
                account.account_id,
                req.group_id,
                "SHARED_WITH",
                {"permission_level": "viewer"},
                schema,
            )
    except AccessDeniedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FinancialAccountResponse(
        id=account.account_id,
        account_type=account.account_type,
        institution=account.institution,
        balance=account.balance,
        currency=account.currency,
        schema_version=attrs["schema_version"],
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
        ensure_group_member(graph, user_id, group_id)
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
