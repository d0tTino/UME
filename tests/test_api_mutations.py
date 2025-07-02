import pytest
from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings


@pytest.fixture
def client_and_graph():
    g = MockGraph()
    configure_graph(g)
    app.state.query_engine = type("QE", (), {"execute_cypher": lambda self, q: []})()
    return TestClient(app), g


def test_create_node_endpoint(client_and_graph):
    client, g = client_and_graph
    token = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    ).json()["access_token"]
    res = client.post(
        "/nodes",
        json={"id": "n1", "attributes": {"x": 1}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert g.get_node("n1") == {"x": 1}


def test_update_node_endpoint(client_and_graph):
    client, g = client_and_graph
    g.add_node("u1", {"a": 1})
    token = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    ).json()["access_token"]
    res = client.patch(
        "/nodes/u1",
        json={"attributes": {"b": 2}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert g.get_node("u1") == {"a": 1, "b": 2}


def test_delete_node_endpoint(client_and_graph):
    client, g = client_and_graph
    g.add_node("d1", {})
    token = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    ).json()["access_token"]
    res = client.delete(
        "/nodes/d1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert g.get_node("d1") is None


def test_create_edge_endpoint(client_and_graph):
    client, g = client_and_graph
    g.add_node("s1", {})
    g.add_node("t1", {})
    token = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    ).json()["access_token"]
    res = client.post(
        "/edges",
        json={"source": "s1", "target": "t1", "label": "L"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert ("s1", "t1", "L") in g.get_all_edges()


def test_delete_edge_endpoint(client_and_graph):
    client, g = client_and_graph
    g.add_node("s2", {})
    g.add_node("t2", {})
    g.add_edge("s2", "t2", "L2")
    token = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    ).json()["access_token"]
    res = client.delete(
        "/edges/s2/t2/L2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert ("s2", "t2", "L2") not in g.get_all_edges()
