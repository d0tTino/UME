import pytest
from fastapi.testclient import TestClient
# ruff: noqa: E402
import sys
import types

sys.modules.setdefault("neo4j", types.ModuleType("neo4j"))
neo4j_mod = sys.modules["neo4j"]
neo4j_mod.GraphDatabase = getattr(neo4j_mod, "GraphDatabase", object)
neo4j_mod.Driver = getattr(neo4j_mod, "Driver", object)

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


def test_post_event_success(client_and_graph):
    client, g = client_and_graph
    token = _token(client)
    event = {
        "event_type": "CREATE_NODE",
        "timestamp": 1,
        "node_id": "n1",
        "payload": {"node_id": "n1", "attributes": {"text": "hi"}},
    }
    res = client.post("/events", json=event, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert g.get_node("n1") == {"text": "hi"}


def test_post_event_invalid(client_and_graph):
    client, _ = client_and_graph
    token = _token(client)
    bad = {"event_type": "CREATE_NODE", "timestamp": "x"}
    res = client.post("/events", json=bad, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400


def test_post_event_requires_auth(client_and_graph):
    client, _ = client_and_graph
    event = {
        "event_type": "CREATE_NODE",
        "timestamp": 1,
        "node_id": "n2",
        "payload": {"node_id": "n2"},
    }
    res = client.post("/events", json=event)
    assert res.status_code == 401
