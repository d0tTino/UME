import pytest
from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings
from ume.models.financial_account import SCHEMA_VERSION

EDGE_VERSION = "3.0.0"


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


def test_create_and_get_financial_account(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    graph.add_node("user1", {})
    graph.add_node(
        "group1", {"type": "UserGroup", "members": ["user1"]}
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
        "schema_version": SCHEMA_VERSION,
    }
    attrs = graph.get_node(account_id)
    assert attrs["account_id"] == account_id
    assert attrs["schema_version"] == SCHEMA_VERSION
    edges = graph.get_all_edges()
    assert (
        account_id,
        "user1",
        "OWNED_BY",
        {"permission_level": "editor", "schema_version": EDGE_VERSION},
    ) in edges
    assert (
        account_id,
        "group1",
        "SHARED_WITH",
        {"permission_level": "viewer", "schema_version": EDGE_VERSION},
    ) in edges

    get_res = client.get(
        f"/v1/accounts/{account_id}",
        params={"user_id": "user1", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_res.status_code == 200
    assert get_res.json()["schema_version"] == SCHEMA_VERSION


def test_create_financial_account_creates_user_node(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    res = client.post(
        "/v1/accounts",
        json={
            "account_type": "savings",
            "institution": "ACME Bank",
            "balance": 50.0,
            "currency": "USD",
            "user_id": "user2",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    account_id = res.json()["id"]
    assert graph.node_exists("user2")
    edges = graph.get_all_edges()
    assert (
        account_id,
        "user2",
        "OWNED_BY",
        {"permission_level": "editor", "schema_version": EDGE_VERSION},
    ) in edges


def test_create_financial_account_rejects_non_member_group(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    graph.add_node("user1", {})
    graph.add_node("group1", {"type": "UserGroup", "members": []})

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


def test_get_financial_account_rejects_non_member_group(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    graph.add_node("user1", {})
    graph.add_node("user2", {})
    graph.add_node("group1", {"type": "UserGroup", "members": ["user1"]})

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
    account_id = res.json()["id"]

    get_res = client.get(
        f"/v1/accounts/{account_id}",
        params={"user_id": "user2", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_res.status_code == 403


def test_create_financial_account_rejects_user_not_in_group_members(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    graph.add_node("user1", {})
    graph.add_node(
        "group1", {"type": "UserGroup", "members": ["user2"]}
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
    assert res.status_code == 403


def test_viewer_cannot_assign_permission_edges_on_account(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    graph.add_node("viewer", {})
    graph.add_node("other_user", {})

    create_res = client.post(
        "/v1/accounts",
        json={
            "account_type": "checking",
            "institution": "ACME Bank",
            "balance": 25.0,
            "currency": "USD",
            "user_id": "owner",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_res.status_code == 200
    account_id = create_res.json()["id"]
    assert create_res.json()["schema_version"] == SCHEMA_VERSION

    graph.add_edge(
        account_id,
        "viewer",
        "SHARED_WITH",
        {"permission_level": "viewer", "schema_version": EDGE_VERSION},
        schema_version=EDGE_VERSION,
    )

    response = client.post(
        "/edges",
        json={
            "source": account_id,
            "target": "other_user",
            "label": "OWNED_BY",
            "attrs": {"permission_level": "editor"},
        },
        headers={"Authorization": f"Bearer {token}"},
        params={"user_id": "viewer"},
    )

    assert response.status_code == 403
    assert response.json()["detail"].startswith(
        "OWNED_BY edges must be bootstrapped"
    )
