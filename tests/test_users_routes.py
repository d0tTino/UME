import pytest
from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings
from ume.models.users import SCHEMA_VERSION as USER_SCHEMA_VERSION
from ume.models.user_group import SCHEMA_VERSION as GROUP_SCHEMA_VERSION
from ume.graph_schema import get_default_edge_version


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
    edge_version = get_default_edge_version("OWNED_BY")

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
    assert user_data["schema_version"] == USER_SCHEMA_VERSION
    attrs = graph.get_node(user_id)
    assert attrs["type"] == "User"
    assert attrs["name"] == "Alice"
    assert attrs["email"] == "alice@example.com"
    assert attrs["schema_version"] == USER_SCHEMA_VERSION

    # Create a user group containing the user
    res = client.post(
        "/v1/groups",
        json={"name": "Team", "members": [user_id], "user_id": user_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    group_data = res.json()
    group_id = group_data["id"]
    assert group_data["members"] == [user_id]
    assert group_data["schema_version"] == GROUP_SCHEMA_VERSION
    attrs = graph.get_node(group_id)
    assert attrs["type"] == "UserGroup"
    assert attrs["name"] == "Team"
    assert attrs["members"] == [user_id]
    assert attrs["schema_version"] == GROUP_SCHEMA_VERSION
    edges = graph.get_all_edges()
    assert (
        group_id,
        user_id,
        "OWNED_BY",
        {"permission_level": "editor", "schema_version": edge_version},
    ) in edges

    # Prepare a resource node and create OWNED_BY edges
    graph.add_node("doc1", {"type": "Document"})
    res = client.post(
        "/v1/owned_by",
        json={"node_id": "doc1", "owner_id": user_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    res = client.post(
        "/v1/owned_by",
        json={"node_id": "doc1", "owner_id": group_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert (
        "doc1",
        user_id,
        "OWNED_BY",
        {"permission_level": "editor"},
    ) not in edges
    assert (
        "doc1",
        group_id,
        "OWNED_BY",
        {"permission_level": "editor"},
    ) not in edges


def test_group_member_add_remove(client_and_graph) -> None:
    client, graph = client_and_graph
    token = _token(client)

    # Create two users
    res = client.post(
        "/v1/users",
        json={"name": "Alice"},
        headers={"Authorization": f"Bearer {token}"},
    )
    user1 = res.json()["id"]
    res = client.post(
        "/v1/users",
        json={"name": "Bob"},
        headers={"Authorization": f"Bearer {token}"},
    )
    user2 = res.json()["id"]

    # Create a group with the first user
    res = client.post(
        "/v1/groups",
        json={"name": "Team", "members": [user1]},
        headers={"Authorization": f"Bearer {token}"},
    )
    group_id = res.json()["id"]

    # Add the second user to the group
    res = client.patch(
        f"/v1/groups/{group_id}/add_member",
        json={"user_id": user2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["members"] == [user1, user2]
    assert graph.get_node(group_id)["members"] == [user1, user2]

    # Adding the same user again should fail
    res = client.patch(
        f"/v1/groups/{group_id}/add_member",
        json={"user_id": user2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400

    # Remove the first user
    res = client.patch(
        f"/v1/groups/{group_id}/remove_member",
        json={"user_id": user1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["members"] == [user2]
    assert graph.get_node(group_id)["members"] == [user2]

    # Removing a non-member should fail
    res = client.patch(
        f"/v1/groups/{group_id}/remove_member",
        json={"user_id": user1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
