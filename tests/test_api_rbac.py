import os
from typing import cast
from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume import MockGraph, RoleBasedGraphAdapter
from ume.config import settings


def build_graph() -> MockGraph:
    g = MockGraph()
    g.add_node("a", {})
    g.add_node("b", {})
    g.add_edge("a", "b", "L")
    return g


def setup_module(_: object) -> None:
    app.state.query_engine = type("QE", (), {"execute_cypher": lambda self, q: []})()
    object.__setattr__(settings, "UME_API_TOKEN", "")


def _token(client: TestClient) -> str:
    res = client.post(
        "/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    )
    return cast(str, res.json()["access_token"])


def teardown_function(_: object) -> None:
    os.environ.pop("UME_API_ROLE", None)
    settings.UME_API_ROLE = None


def test_shortest_path_allowed_for_analytics_agent() -> None:
    os.environ["UME_API_ROLE"] = "AnalyticsAgent"
    settings.UME_API_ROLE = "AnalyticsAgent"
    configure_graph(build_graph())

    client = TestClient(app)
    token = _token(client)
    payload = {"source": "a", "target": "b"}
    res = client.post(
        "/analytics/shortest_path",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == {"path": ["a", "b"]}


def test_path_and_subgraph_allowed_for_analytics_agent() -> None:
    os.environ["UME_API_ROLE"] = "AnalyticsAgent"
    settings.UME_API_ROLE = "AnalyticsAgent"
    configure_graph(build_graph())

    client = TestClient(app)
    token = _token(client)
    payload = {"source": "a", "target": "b"}
    res = client.post(
        "/analytics/path",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == {"path": ["a", "b"]}

    sub = {"start": "a", "depth": 1}
    res = client.post(
        "/analytics/subgraph",
        json=sub,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert set(res.json()["nodes"].keys()) == {"a", "b"}


def test_shortest_path_forbidden_for_other_roles() -> None:
    os.environ["UME_API_ROLE"] = "AutoDev"
    settings.UME_API_ROLE = "AutoDev"
    configure_graph(build_graph())

    client = TestClient(app)
    token = _token(client)
    payload = {"source": "a", "target": "b"}
    res = client.post(
        "/analytics/shortest_path",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403

    res = client.post(
        "/analytics/path",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403

    sub = {"start": "a", "depth": 1}
    res = client.post(
        "/analytics/subgraph",
        json=sub,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_path_forbidden_with_role_based_adapter() -> None:
    graph = RoleBasedGraphAdapter(build_graph(), role="AutoDev")
    configure_graph(graph)

    client = TestClient(app)
    token = _token(client)
    payload = {"source": "a", "target": "b"}
    res = client.post(
        "/analytics/path",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_subgraph_forbidden_with_role_based_adapter() -> None:
    graph = RoleBasedGraphAdapter(build_graph(), role="AutoDev")
    configure_graph(graph)

    client = TestClient(app)
    token = _token(client)
    sub = {"start": "a", "depth": 1}
    res = client.post(
        "/analytics/subgraph",
        json=sub,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_redact_node_forbidden_with_role_based_adapter() -> None:
    graph = RoleBasedGraphAdapter(build_graph(), role="AutoDev")
    configure_graph(graph)

    client = TestClient(app)
    token = _token(client)
    res = client.post(
        "/redact/node/a",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_redact_edge_forbidden_with_role_based_adapter() -> None:
    graph = RoleBasedGraphAdapter(build_graph(), role="AutoDev")
    configure_graph(graph)

    client = TestClient(app)
    token = _token(client)
    res = client.post(
        "/redact/edge",
        json={"source": "a", "target": "b", "label": "L"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
