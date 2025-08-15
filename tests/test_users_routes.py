import pytest
from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings


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


def test_user_group_and_owned_by(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    # Create a user
    res = client.post(
        "/v1/users",
        json={"name": "Alice", "email": "alice@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    user_data = res.json()
    user_id = user_data["id"]
    assert user_data["name"] == "Alice"
    assert user_data["email"] == "alice@example.com"
    attrs = graph.get_node(user_id)
    assert attrs["type"] == "User"
    assert attrs["name"] == "Alice"
    assert attrs["email"] == "alice@example.com"

    # Create a user group containing the user
    res = client.post(
        "/v1/groups",
        json={"name": "Team", "members": [user_id]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    group_data = res.json()
    group_id = group_data["id"]
    assert group_data["members"] == [user_id]
    attrs = graph.get_node(group_id)
    assert attrs["type"] == "UserGroup"
    assert attrs["name"] == "Team"
    assert attrs["members"] == [user_id]

    # Prepare a resource node and create OWNED_BY edges
    graph.add_node("doc1", {"type": "Document"})
    res = client.post(
        "/v1/owned_by",
        json={"node_id": "doc1", "owner_id": user_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    res = client.post(
        "/v1/owned_by",
        json={"node_id": "doc1", "owner_id": group_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    edges = graph.get_all_edges()
    assert ("doc1", user_id, "OWNED_BY", {"permission_level": "public"}) in edges
    assert ("doc1", group_id, "OWNED_BY", {"permission_level": "public"}) in edges
