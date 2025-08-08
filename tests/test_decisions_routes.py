from fastapi.testclient import TestClient
import pytest

from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings


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
        json={"query": "Choose option"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    analysis = res.json()
    analysis_id = analysis["analysis_id"]

    res = client.post(
        f"/v1/decisions/{analysis_id}/actions",
        json={"description": "Option A"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    action = res.json()
    action_id = action["action_id"]

    res = client.get(
        f"/v1/decisions/{analysis_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["analysis"]["analysis_id"] == analysis_id
    assert len(data["actions"]) == 1
    assert data["actions"][0]["action_id"] == action_id

    assert g.get_node(analysis_id)["query"] == "Choose option"
    assert g.get_node(action_id)["description"] == "Option A"
    assert g.find_connected_nodes(analysis_id, edge_label="CONSIDERS") == [action_id]
