from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from . import api_deps as deps
from .graph_adapter import IGraphAdapter
from .permissions_adapter import PermissionsGraphAdapter
from .models import create_financial_account

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


@router.post("", response_model=FinancialAccountResponse)
def create_account(
    req: FinancialAccountCreateRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: str = Depends(deps.get_current_role),
) -> FinancialAccountResponse:
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
    }
    graph.add_node(account.account_id, attrs)
    graph.add_edge(
        account.account_id,
        req.user_id,
        "OWNED_BY",
        {"permission_level": "editor"},
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
    )
