from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ume.api import app, configure_graph
from ume.decisions_routes import router as decisions_router
from ume import MockGraph
from ume.config import settings
import ume.api_deps as deps
from ume.graph_adapter import IGraphAdapter
from ume.permissions_adapter import PermissionsGraphAdapter
from ume.models import create_financial_account
from ume.models.decision_analysis import SCHEMA_VERSION

# Register decision routes once for tests
if not any(r.path.startswith("/v1/decisions") for r in app.router.routes):
    app.include_router(decisions_router)

accounts_router = APIRouter(prefix="/v1/accounts")


class AccountCreateRequest(BaseModel):
    user_id: str
    group_id: str | None = None
    account_type: str = "checking"
    institution: str = "Bank"
    balance: float = 0.0


@accounts_router.post("")
def create_account(
    req: AccountCreateRequest,
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: str = Depends(deps.get_current_role),
) -> dict[str, str]:
    account = create_financial_account(
        req.account_type, req.institution, req.balance
    )
    graph.add_node(
        account.account_id,
        {
            "type": "FinancialAccount",
            "account_type": account.account_type,
            "institution": account.institution,
            "balance": account.balance,
            "currency": account.currency,
        },
    )
    graph.add_edge(
        account.account_id,
        req.user_id,
        "OWNED_BY",
        {"permission_level": "editor"},
    )
    if req.group_id:
        graph.add_edge(
            account.account_id,
            req.group_id,
            "SHARED_WITH",
            {"permission_level": "viewer"},
        )
    return {"id": account.account_id}


@accounts_router.get("/{account_id}")
def get_account(
    account_id: str,
    user_id: str = Query(...),
    group_id: str | None = Query(None),
    graph: IGraphAdapter = Depends(deps.get_graph),
    _: str = Depends(deps.get_current_role),
) -> dict[str, str | float]:
    perm_graph = PermissionsGraphAdapter(
        graph, user_id=user_id, group_id=group_id
    )
    attrs = perm_graph.get_node(account_id)
    if attrs is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return attrs


if not any(r.path.startswith("/v1/accounts") for r in app.router.routes):
    app.include_router(accounts_router)


def _token(client: TestClient) -> str:
    res = client.post(
        "/auth/token",
        data={
            "username": settings.UME_OAUTH_USERNAME,
            "password": settings.UME_OAUTH_PASSWORD,
        },
    )
    return res.json()["access_token"]


@pytest.fixture
def client_and_graph():
    graph = MockGraph()
    configure_graph(graph)
    return TestClient(app), graph


def test_calendar_mixed_access(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    graph.add_node("owner", {})
    graph.add_node("other", {})
    graph.add_node(
        "group1", {"type": "UserGroup", "members": ["owner", "other"]}
    )

    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat()

    res = client.post(
        "/v1/calendar/events",
        json={"title": "Meeting", "start_time": start, "user_id": "owner", "group_id": "group1"},
    )
    assert res.status_code == 401

    res = client.post(
        "/v1/calendar/events",
        json={"title": "Meeting", "start_time": start, "user_id": "owner", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    event_id = res.json()["event_id"]

    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "other"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == []

    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "other", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()[0]["event_id"] == event_id

    res = client.get(
        "/v1/calendar/events",
        params={"user_id": "owner"},
    )
    assert res.status_code == 401


def test_decision_mixed_access(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    graph.add_node("u1", {})
    graph.add_node("u2", {})
    graph.add_node("g1", {"type": "UserGroup", "members": ["u1", "u2"]})

    res = client.post(
        "/v1/decisions",
        json={"query": "test", "user_id": "u1", "group_id": "g1"},
    )
    assert res.status_code == 401

    res = client.post(
        "/v1/decisions",
        json={"query": "test", "user_id": "u1", "group_id": "g1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    analysis_resp = res.json()
    analysis_id = analysis_resp["analysis_id"]
    assert analysis_resp["schema_version"] == SCHEMA_VERSION

    res = client.get(
        f"/v1/decisions/{analysis_id}",
        params={"user_id": "u2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404

    res = client.get(
        f"/v1/decisions/{analysis_id}",
        params={"user_id": "u2", "group_id": "g1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["analysis"]["schema_version"] == SCHEMA_VERSION

    res = client.get(
        f"/v1/decisions/{analysis_id}",
        params={"user_id": "u1"},
    )
    assert res.status_code == 401


def test_financial_account_mixed_access(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    graph.add_node("u1", {})
    graph.add_node("u2", {})
    graph.add_node(
        "group1", {"type": "UserGroup", "members": ["u1", "u2"]}
    )
    graph.add_edge("group1", "u1", "SHARED_WITH", {"permission_level": "editor"})
    graph.add_edge("group1", "u2", "SHARED_WITH", {"permission_level": "viewer"})

    res = client.post(
        "/v1/accounts",
        json={
            "user_id": "u1",
            "group_id": "group1",
            "account_type": "checking",
            "institution": "Bank",
            "balance": 0.0,
        },
    )
    assert res.status_code == 401

    res = client.post(
        "/v1/accounts",
        json={
            "user_id": "u1",
            "group_id": "group1",
            "account_type": "checking",
            "institution": "Bank",
            "balance": 0.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    account_id = res.json()["id"]

    res = client.get(
        f"/v1/accounts/{account_id}",
        params={"user_id": "u2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404

    res = client.get(
        f"/v1/accounts/{account_id}",
        params={"user_id": "u2", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["account_type"] == "checking"

    res = client.get(
        f"/v1/accounts/{account_id}",
        params={"user_id": "u1"},
    )
    assert res.status_code == 401
