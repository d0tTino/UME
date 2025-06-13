import os
from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume import MockGraph, RoleBasedGraphAdapter
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


def test_path_and_subgraph_allowed_for_analytics_agent():
    os.environ["UME_API_ROLE"] = "AnalyticsAgent"
    configure_graph(build_graph())

    client = TestClient(app)
    payload = {"source": "a", "target": "b"}
    res = client.post(
        "/analytics/path",
        json=payload,
        headers={"Authorization": f"Bearer {settings.UME_API_TOKEN}"},
    )
    assert res.status_code == 200
    assert res.json() == {"path": ["a", "b"]}

    sub = {"start": "a", "depth": 1}
    res = client.post(
        "/analytics/subgraph",
        json=sub,
        headers={"Authorization": f"Bearer {settings.UME_API_TOKEN}"},
    )
    assert res.status_code == 200
    assert set(res.json()["nodes"].keys()) == {"a", "b"}


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

    res = client.post(
        "/analytics/path",
        json=payload,
        headers={"Authorization": f"Bearer {settings.UME_API_TOKEN}"},
    )
    assert res.status_code == 403

    sub = {"start": "a", "depth": 1}
    res = client.post(
        "/analytics/subgraph",
        json=sub,
        headers={"Authorization": f"Bearer {settings.UME_API_TOKEN}"},
    )
    assert res.status_code == 403


def test_path_forbidden_with_role_based_adapter():
    graph = RoleBasedGraphAdapter(build_graph(), role="AutoDev")
    configure_graph(graph)

    client = TestClient(app)
    payload = {"source": "a", "target": "b"}
    res = client.post(
        "/analytics/path",
        json=payload,
        headers={"Authorization": f"Bearer {settings.UME_API_TOKEN}"},
    )
    assert res.status_code == 403


def test_subgraph_forbidden_with_role_based_adapter():
    graph = RoleBasedGraphAdapter(build_graph(), role="AutoDev")
    configure_graph(graph)

    client = TestClient(app)
    sub = {"start": "a", "depth": 1}
    res = client.post(
        "/analytics/subgraph",
        json=sub,
        headers={"Authorization": f"Bearer {settings.UME_API_TOKEN}"},
    )
    assert res.status_code == 403


def test_redact_node_forbidden_with_role_based_adapter():
    graph = RoleBasedGraphAdapter(build_graph(), role="AutoDev")
    configure_graph(graph)

    client = TestClient(app)
    res = client.post(
        "/redact/node/a",
        headers={"Authorization": f"Bearer {settings.UME_API_TOKEN}"},
    )
    assert res.status_code == 403


def test_redact_edge_forbidden_with_role_based_adapter():
    graph = RoleBasedGraphAdapter(build_graph(), role="AutoDev")
    configure_graph(graph)

    client = TestClient(app)
    res = client.post(
        "/redact/edge",
        json={"source": "a", "target": "b", "label": "L"},
        headers={"Authorization": f"Bearer {settings.UME_API_TOKEN}"},
    )
    assert res.status_code == 403
