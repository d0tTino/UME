from fastapi.testclient import TestClient
import pytest

from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings
from ume.models.decision_analysis import SCHEMA_VERSION
from ume.models.proposed_action import SCHEMA_VERSION as ACTION_SCHEMA_VERSION


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


def test_decision_group_flow(client_and_graph) -> None:
    client, g = client_and_graph
    token = _token(client)
    g.add_node("group1", {"members": ["user1"]})

    # Create decision with group_id
    res = client.post(
        "/v1/decisions",
        json={"query": "Choose", "user_id": "user1", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    analysis_id = res.json()["analysis_id"]

    # Add action with group_id
    res = client.post(
        f"/v1/decisions/{analysis_id}/actions",
        json={"description": "Act", "user_id": "user1", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    action_id = res.json()["action_id"]

    # Retrieve decision with group_id
    res = client.get(
        f"/v1/decisions/{analysis_id}",
        params={"user_id": "user1", "group_id": "group1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["analysis"]["analysis_id"] == analysis_id
    assert data["analysis"]["schema_version"] == SCHEMA_VERSION
    assert len(data["actions"]) == 1
    assert data["actions"][0]["action_id"] == action_id
    assert data["actions"][0]["schema_version"] == ACTION_SCHEMA_VERSION

    # Graph contains expected nodes and edges
    assert g.get_node(analysis_id)["query"] == "Choose"
    assert g.get_node(action_id)["description"] == "Act"
    edges = g.get_all_edges()
    assert any(
        s == analysis_id
        and t == "group1"
        and lbl == "SHARED_WITH"
        and e.get("permission_level") == "editor"
        for s, t, lbl, e in edges
    )
    assert any(
        s == action_id
        and t == "group1"
        and lbl == "SHARED_WITH"
        and e.get("permission_level") == "viewer"
        for s, t, lbl, e in edges
    )
