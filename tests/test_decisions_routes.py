from fastapi.testclient import TestClient
import pytest

from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings
from ume.models.decision_analysis import SCHEMA_VERSION
from ume.models.proposed_action import SCHEMA_VERSION as ACTION_SCHEMA_VERSION
from ume.models.user_group import SCHEMA_VERSION as GROUP_SCHEMA_VERSION
from ume.models.users import SCHEMA_VERSION as USER_SCHEMA_VERSION
from ume.decisions_routes import EDGE_VERSION


def _token(client: TestClient) -> str:
    res = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    )
    return res.json()["access_token"]


@pytest.fixture
def client_and_graph():
    g = MockGraph()
    configure_graph(g)
    return TestClient(app), g


def test_decision_flow(client_and_graph) -> None:
    client, g = client_and_graph
    token = _token(client)

    res = client.post(
        "/v1/decisions",
        json={"query": "Choose option", "user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    analysis = res.json()
    analysis_id = analysis["analysis_id"]
    assert analysis["type"] == "DecisionAnalysis"
    assert analysis["schema_version"] == SCHEMA_VERSION
    user_attrs = g.get_node("user1")
    assert user_attrs is not None
    assert user_attrs["type"] == "User"
    assert user_attrs["schema_version"] == USER_SCHEMA_VERSION
    assert user_attrs["user_id"] == "user1"
    assert user_attrs["name"] == "user1"
    assert isinstance(user_attrs["created_at"], int)

    res = client.post(
        f"/v1/decisions/{analysis_id}/actions",
        json={"description": "Option A", "user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    action = res.json()
    action_id = action["action_id"]
    assert action["type"] == "ProposedAction"
    assert action["schema_version"] == ACTION_SCHEMA_VERSION

    res = client.get(
        f"/v1/decisions/{analysis_id}",
        params={"user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["analysis"]["analysis_id"] == analysis_id
    assert data["analysis"]["type"] == "DecisionAnalysis"
    assert data["analysis"]["schema_version"] == SCHEMA_VERSION
    assert len(data["actions"]) == 1
    assert data["actions"][0]["action_id"] == action_id
    assert data["actions"][0]["type"] == "ProposedAction"
    assert data["actions"][0]["schema_version"] == ACTION_SCHEMA_VERSION

    analysis_attrs = g.get_node(analysis_id)
    assert analysis_attrs is not None
    assert analysis_attrs["type"] == "DecisionAnalysis"
    assert g.get_node(analysis_id)["query"] == "Choose option"
    action_attrs = g.get_node(action_id)
    assert action_attrs is not None
    assert action_attrs["type"] == "ProposedAction"
    assert action_attrs["description"] == "Option A"
    assert g.find_connected_nodes(analysis_id, edge_label="CONSIDERS") == [action_id]
    # Permission edges created
    edges = g.get_all_edges()
    assert any(
        s == analysis_id
        and t == "user1"
        and lbl == "OWNED_BY"
        and e.get("permission_level") == "editor"
        for s, t, lbl, e in edges
    )
    assert any(
        s == action_id
        and t == "user1"
        and lbl == "OWNED_BY"
        and e.get("permission_level") == "editor"
        for s, t, lbl, e in edges
    )


def test_decision_flow_with_group(client_and_graph) -> None:
    client, g = client_and_graph
    token = _token(client)
    g.add_node("group1", {"members": ["user1", "user2"]})

    res = client.post(
        "/v1/decisions",
        json={"query": "Choose", "user_id": "user1", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    analysis_id = res.json()["analysis_id"]
    group_attrs = g.get_node("group1")
    assert group_attrs is not None
    assert group_attrs["type"] == "UserGroup"
    assert group_attrs["schema_version"] == GROUP_SCHEMA_VERSION
    assert group_attrs["group_id"] == "group1"
    assert group_attrs["name"] == "group1"
    assert group_attrs["members"] == ["user1", "user2"]

    edges = g.get_all_edges()
    assert any(
        s == analysis_id
        and t == "group1"
        and lbl == "SHARED_WITH"
        and e.get("permission_level") == "editor"
        for s, t, lbl, e in edges
    )

    res = client.get(
        f"/v1/decisions/{analysis_id}",
        params={"user_id": "user1", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    # Group editor can add an action and share it back with editor access
    res = client.post(
        f"/v1/decisions/{analysis_id}/actions",
        json={
            "description": "Team option",
            "user_id": "user2",
            "group_id": "group1",
            "group_permission_level": "editor",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    action_id = res.json()["action_id"]

    edges = g.get_all_edges()
    assert any(
        s == action_id
        and t == "group1"
        and lbl == "SHARED_WITH"
        and e.get("permission_level") == "editor"
        for s, t, lbl, e in edges
    )


def test_decision_group_viewer_share_limits_editing(client_and_graph) -> None:
    client, g = client_and_graph
    token = _token(client)
    g.add_node("group1", {"members": ["user1", "user2"]})

    res = client.post(
        "/v1/decisions",
        json={
            "query": "Choose",
            "user_id": "user1",
            "group_id": "group1",
            "group_permission_level": "viewer",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    analysis_id = res.json()["analysis_id"]

    edges = g.get_all_edges()
    assert any(
        s == analysis_id
        and t == "group1"
        and lbl == "SHARED_WITH"
        and e.get("permission_level") == "viewer"
        for s, t, lbl, e in edges
    )

    nodes_before = set(g.get_all_node_ids())
    res = client.post(
        f"/v1/decisions/{analysis_id}/actions",
        json={"description": "Team option", "user_id": "user2", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    nodes_after = set(g.get_all_node_ids())
    new_nodes = nodes_after - nodes_before
    assert new_nodes <= {"user2"}
    assert not any(
        (g.get_node(node_id) or {}).get("type") == "ProposedAction"
        for node_id in new_nodes
    )

    res = client.post(
        f"/v1/decisions/{analysis_id}/actions",
        json={
            "description": "Owner action",
            "user_id": "user1",
            "group_id": "group1",
            "group_permission_level": "viewer",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    action_id = res.json()["action_id"]

    edges = g.get_all_edges()
    assert any(
        s == action_id
        and t == "group1"
        and lbl == "SHARED_WITH"
        and e.get("permission_level") == "viewer"
        for s, t, lbl, e in edges
    )


def test_add_action_preserves_outcome_metrics(client_and_graph) -> None:
    client, g = client_and_graph
    token = _token(client)

    res = client.post(
        "/v1/decisions",
        json={"query": "Q", "user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    analysis_id = res.json()["analysis_id"]

    metrics_payload = {"score": 1, "notes": "high", "metadata": {"tags": ["x"]}}
    res = client.post(
        f"/v1/decisions/{analysis_id}/actions",
        json={
            "description": "Act",
            "user_id": "user1",
            "outcome_metrics": metrics_payload,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    action_id = res.json()["action_id"]
    assert res.json()["outcome_metrics"] == metrics_payload

    node_attrs = g.get_node(action_id)
    assert node_attrs is not None
    assert node_attrs["outcome_metrics"] == metrics_payload


def test_group_membership_required(client_and_graph) -> None:
    client, g = client_and_graph
    token = _token(client)
    g.add_node("group2", {"members": ["user2"]})

    res = client.post(
        "/v1/decisions",
        json={"query": "X", "user_id": "user2", "group_id": "group2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    analysis_id = res.json()["analysis_id"]

    res = client.post(
        "/v1/decisions",
        json={"query": "Y", "user_id": "user1", "group_id": "group2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403

    res = client.get(
        f"/v1/decisions/{analysis_id}",
        params={"user_id": "user1", "group_id": "group2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_group_missing_returns_404(client_and_graph) -> None:
    client, g = client_and_graph
    token = _token(client)

    res = client.post(
        "/v1/decisions",
        json={"query": "Z", "user_id": "user1", "group_id": "missing"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 404
    assert res.json() == {"detail": "Group not found"}


def test_add_action_requires_group_membership(client_and_graph) -> None:
    client, g = client_and_graph
    token = _token(client)
    g.add_node("group1", {"members": ["user2"]})

    res = client.post(
        "/v1/decisions",
        json={"query": "Q", "user_id": "user2", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    analysis_id = res.json()["analysis_id"]

    res = client.post(
        f"/v1/decisions/{analysis_id}/actions",
        json={"description": "Act", "user_id": "user1", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_viewer_cannot_add_action(client_and_graph) -> None:
    client, g = client_and_graph
    token = _token(client)

    res = client.post(
        "/v1/decisions",
        json={"query": "Q", "user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    analysis_id = res.json()["analysis_id"]

    g.add_node("user2", {})
    g.add_edge(
        analysis_id,
        "user2",
        "SHARED_WITH",
        {"permission_level": "viewer"},
        schema_version=EDGE_VERSION,
    )

    nodes_before = set(g.get_all_node_ids())
    res = client.post(
        f"/v1/decisions/{analysis_id}/actions",
        json={"description": "Act", "user_id": "user2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    nodes_after = set(g.get_all_node_ids())
    assert nodes_after == nodes_before
    user2_attrs = g.get_node("user2")
    assert user2_attrs is not None
    assert user2_attrs["type"] == "User"
    assert user2_attrs["schema_version"] == USER_SCHEMA_VERSION
    proposed_action_nodes = [
        node_id
        for node_id in nodes_after
        if (
            (node_attrs := g.get_node(node_id))
            and {"description", "rank", "is_optimal", "outcome_metrics"}.issubset(node_attrs.keys())
        )
    ]
    assert proposed_action_nodes == []
    assert all(lbl != "CONSIDERS" for _, _, lbl, _ in g.get_all_edges())
