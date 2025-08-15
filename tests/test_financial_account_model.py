import pytest
from fastapi.testclient import TestClient

from ume.models import FinancialAccount, create_financial_account
from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings


def test_create_financial_account() -> None:
    account = create_financial_account("checking", "ACME Bank", 100.0)
    assert isinstance(account, FinancialAccount)
    assert account.account_type == "checking"
    assert account.institution == "ACME Bank"
    assert account.balance == 100.0
    assert account.currency == "USD"
    assert account.account_id


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


def test_create_financial_account_edges(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    graph.add_node("user1", {})
    graph.add_node("group1", {})
    graph.add_edge(
        "group1", "user1", "SHARED_WITH", {"permission_level": "editor"}
    )

    res = client.post(
        "/v1/accounts",
        json={
            "account_type": "checking",
            "institution": "ACME Bank",
            "balance": 100.0,
            "currency": "USD",
            "user_id": "user1",
            "group_id": "group1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    account_id = data["id"]
    assert data == {
        "id": account_id,
        "account_type": "checking",
        "institution": "ACME Bank",
        "balance": 100.0,
        "currency": "USD",
    }
    edges = graph.get_all_edges()
    assert (
        account_id,
        "user1",
        "OWNED_BY",
        {"permission_level": "editor"},
    ) in edges
    assert (
        account_id,
        "group1",
        "SHARED_WITH",
        {"permission_level": "viewer"},
    ) in edges


def test_financial_account_group_requires_editor(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    graph.add_node("user1", {})
    graph.add_node("group1", {})

    res = client.post(
        "/v1/accounts",
        json={
            "account_type": "checking",
            "institution": "ACME Bank",
            "balance": 100.0,
            "currency": "USD",
            "user_id": "user1",
            "group_id": "group1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
