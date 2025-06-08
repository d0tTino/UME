import os
from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings


def build_graph():
    g = MockGraph()
    g.add_node("a", {})
    g.add_node("b", {})
    g.add_edge("a", "b", "L")
    return g


def setup_module(_):
    app.state.query_engine = type("QE", (), {"execute_cypher": lambda self, q: []})()


def teardown_function(_):
    os.environ.pop("UME_API_ROLE", None)


def test_shortest_path_allowed_for_analytics_agent():
    os.environ["UME_API_ROLE"] = "AnalyticsAgent"
    configure_graph(build_graph())

    client = TestClient(app)
    payload = {"source": "a", "target": "b"}
    res = client.post(
        "/analytics/shortest_path",
        json=payload,
        headers={"Authorization": f"Bearer {settings.UME_API_TOKEN}"},
    )
    assert res.status_code == 200
    assert res.json() == {"path": ["a", "b"]}


def test_shortest_path_forbidden_for_other_roles():
    os.environ["UME_API_ROLE"] = "AutoDev"
    configure_graph(build_graph())

    client = TestClient(app)
    payload = {"source": "a", "target": "b"}
    res = client.post(
        "/analytics/shortest_path",
        json=payload,
        headers={"Authorization": f"Bearer {settings.UME_API_TOKEN}"},
    )
    assert res.status_code == 403
