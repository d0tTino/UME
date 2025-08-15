from fastapi.testclient import TestClient
import pytest

from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings
from ume.models.decision_analysis import SCHEMA_VERSION


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
    assert analysis["schema_version"] == SCHEMA_VERSION

    res = client.post(
        f"/v1/decisions/{analysis_id}/actions",
        json={"description": "Option A", "user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    action = res.json()
    action_id = action["action_id"]

    res = client.get(
        f"/v1/decisions/{analysis_id}",
        params={"user_id": "user1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["analysis"]["analysis_id"] == analysis_id
    assert data["analysis"]["schema_version"] == SCHEMA_VERSION
    assert len(data["actions"]) == 1
    assert data["actions"][0]["action_id"] == action_id

    assert g.get_node(analysis_id)["query"] == "Choose option"
    assert g.get_node(action_id)["description"] == "Option A"
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
