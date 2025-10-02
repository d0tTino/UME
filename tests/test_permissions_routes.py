import pytest
from fastapi.testclient import TestClient

from ume import AccessDeniedError, MockGraph, PermissionsGraphAdapter
from ume.api import app, configure_graph
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


def _seed_graph(graph: MockGraph) -> None:
    # Subjects
    graph.add_node("user1", {"type": "User"})
    graph.add_node("group1", {"type": "UserGroup", "members": ["user1"]})
    graph.add_node("other", {"type": "User"})

    # User-only nodes
    graph.add_node("u_viewer", {})
    graph.add_edge("u_viewer", "user1", "OWNED_BY", {"permission_level": "viewer"})
    graph.add_node("u_editor", {})
    graph.add_edge("u_editor", "user1", "OWNED_BY", {"permission_level": "editor"})
    graph.add_node("u_no_perm", {})
    graph.add_edge("u_no_perm", "user1", "OWNED_BY", {})
    graph.add_node("u_invalid", {})
    graph.add_edge("u_invalid", "user1", "OWNED_BY", {"permission_level": "invalid"})

    # Group-only nodes
    graph.add_node("g_viewer", {})
    graph.add_edge("g_viewer", "group1", "SHARED_WITH", {"permission_level": "viewer"})
    graph.add_node("g_editor", {})
    graph.add_edge("g_editor", "group1", "SHARED_WITH", {"permission_level": "editor"})
    graph.add_node("g_no_perm", {})
    graph.add_edge("g_no_perm", "group1", "SHARED_WITH", {})
    graph.add_node("g_invalid", {})
    graph.add_edge("g_invalid", "group1", "SHARED_WITH", {"permission_level": "invalid"})

    # Mixed node accessible to both
    graph.add_node("mixed", {})
    graph.add_edge("mixed", "user1", "OWNED_BY", {"permission_level": "viewer"})
    graph.add_edge("mixed", "group1", "SHARED_WITH", {"permission_level": "editor"})

    # Node unrelated to tested subjects
    graph.add_node("unrelated", {})
    graph.add_edge("unrelated", "other", "OWNED_BY", {"permission_level": "viewer"})


def test_get_nodes_by_user_filters_viewer_editor(client_and_graph):
    client, graph = client_and_graph
    _seed_graph(graph)
    token = _token(client)

    res = client.get(
        "/v1/nodes",
        params={"user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert set(res.json()["nodes"]) == {"u_viewer", "u_editor", "mixed"}


def test_get_nodes_shared_with_filters_viewer_editor(client_and_graph):
    client, graph = client_and_graph
    _seed_graph(graph)
    token = _token(client)

    res = client.get(
        "/v1/nodes/shared",
        params={"user_id": "user1", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert set(res.json()["nodes"]) == {"g_viewer", "g_editor", "mixed"}


def test_get_nodes_by_user_excludes_nodes_without_permission_level(client_and_graph):
    client, graph = client_and_graph
    _seed_graph(graph)
    token = _token(client)

    res = client.get(
        "/v1/nodes",
        params={"user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    nodes = set(res.json()["nodes"])
    assert "u_no_perm" not in nodes
    assert "u_invalid" not in nodes


def test_get_nodes_shared_with_excludes_nodes_without_permission_level(
    client_and_graph,
) -> None:
    client, graph = client_and_graph
    _seed_graph(graph)
    token = _token(client)

    res = client.get(
        "/v1/nodes/shared",
        params={"user_id": "user1", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    nodes = set(res.json()["nodes"])
    assert "g_no_perm" not in nodes
    assert "g_invalid" not in nodes


def test_get_nodes_shared_with_requires_group_membership(client_and_graph) -> None:
    client, graph = client_and_graph
    _seed_graph(graph)
    token = _token(client)

    res = client.get(
        "/v1/nodes/shared",
        params={"user_id": "other", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 403


def test_editor_vs_viewer_permissions(client_and_graph) -> None:
    _, graph = client_and_graph
    _seed_graph(graph)
    perm_graph = PermissionsGraphAdapter(graph, user_id="user1")

    with pytest.raises(AccessDeniedError):
        perm_graph.update_node("u_viewer", {"attr": 1})

    perm_graph.update_node("u_editor", {"attr": 2})
