import pytest
from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings


@pytest.fixture
def client_and_graph():
    g = MockGraph()
    g.add_node("a", {})
    g.add_node("b", {})
    g.add_edge("a", "b", "L")
    configure_graph(g)
    app.state.query_engine = type("QE", (), {"execute_cypher": lambda self, q: []})()
    return TestClient(app), g


def test_redact_node_endpoint(client_and_graph):
    client, g = client_and_graph
    token = client.post(
        "/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    ).json()["access_token"]
    res = client.post(
        "/redact/node/a",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert g.get_node("a") is None


def test_redact_edge_endpoint(client_and_graph):
    client, g = client_and_graph
    token = client.post(
        "/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    ).json()["access_token"]
    res = client.post(
        "/redact/edge",
        json={"source": "a", "target": "b", "label": "L"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert g.get_all_edges() == []
