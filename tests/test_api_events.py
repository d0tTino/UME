import pytest
from fastapi.testclient import TestClient
# ruff: noqa: E402
import sys
import types
import importlib.util
from pathlib import Path

base = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(base / "src" / "ume_client"))
sys.path.insert(0, str(base / "src"))

spec_ev = importlib.util.spec_from_file_location(
    "events_pb2", base / "src" / "ume_client" / "events_pb2.py"
)
assert spec_ev and spec_ev.loader
events_pb2 = importlib.util.module_from_spec(spec_ev)
spec_ev.loader.exec_module(events_pb2)
sys.modules["events_pb2"] = events_pb2

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
        "eventType": "CREATE_NODE",
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
    bad = {"eventType": "CREATE_NODE", "timestamp": "x"}
    res = client.post("/events", json=bad, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400


def test_post_event_requires_auth(client_and_graph):
    client, _ = client_and_graph
    event = {
        "eventType": "CREATE_NODE",
        "timestamp": 1,
        "node_id": "n2",
        "payload": {"node_id": "n2"},
    }
    res = client.post("/events", json=event)
    assert res.status_code == 401


def test_post_events_batch(client_and_graph) -> None:
    client, g = client_and_graph
    token = _token(client)
    events = [
        {
            "eventType": "CREATE_NODE",
            "timestamp": 1,
            "node_id": "n1",
            "payload": {"node_id": "n1", "attributes": {"text": "a"}},
        },
        {
            "eventType": "CREATE_NODE",
            "timestamp": 2,
            "node_id": "n2",
            "payload": {"node_id": "n2", "attributes": {"text": "b"}},
        },
    ]
    res = client.post(
        "/events/batch",
        json=events,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert g.get_node("n1") == {"text": "a"}
    assert g.get_node("n2") == {"text": "b"}


def test_post_events_batch_invalid(client_and_graph) -> None:
    client, _ = client_and_graph
    token = _token(client)
    events = [
        {"eventType": "CREATE_NODE", "timestamp": "bad"}
    ]
    res = client.post(
        "/events/batch",
        json=events,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400


def test_post_event_missing_field(client_and_graph) -> None:
    client, _ = client_and_graph
    token = _token(client)
    res = client.post(
        "/events",
        json={"timestamp": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400


def test_store_event_success(client_and_graph) -> None:
    client, g = client_and_graph
    token = _token(client)
    event = {
        "eventType": "CREATE_NODE",
        "timestamp": 1,
        "node_id": "n3",
        "payload": {"node_id": "n3", "attributes": {"text": "store"}},
    }
    res = client.post("/store", json=event, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert g.get_node("n3") == {"text": "store"}


def test_store_events_batch(client_and_graph) -> None:
    client, g = client_and_graph
    token = _token(client)
    events = [
        {
            "eventType": "CREATE_NODE",
            "timestamp": 1,
            "node_id": "n4",
            "payload": {"node_id": "n4", "attributes": {"text": "x"}},
        },
        {
            "eventType": "CREATE_NODE",
            "timestamp": 2,
            "node_id": "n5",
            "payload": {"node_id": "n5", "attributes": {"text": "y"}},
        },
    ]
    res = client.post(
        "/store/batch",
        json=events,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert g.get_node("n4") == {"text": "x"}
    assert g.get_node("n5") == {"text": "y"}
