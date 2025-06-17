from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings


def setup_module(_):
    # configure app state for tests
    app.state.query_engine = type(
        "QE", (), {"execute_cypher": lambda self, q: [{"q": q}]}
    )()
    g = MockGraph()
    g.add_node("a", {})
    g.add_node("b", {})
    g.add_edge("a", "b", "L")
    configure_graph(g)


def test_run_query_authorized():
    client = TestClient(app)
    res = client.get(
        "/query",
        params={"cypher": "MATCH (n) RETURN n"},
        headers={"Authorization": f"Bearer {settings.UME_API_TOKEN}"},
    )
    assert res.status_code == 200
    assert res.json() == [{"q": "MATCH (n) RETURN n"}]


def test_run_query_unauthorized():
    client = TestClient(app)
    res = client.get("/query", params={"cypher": "MATCH (n)"})
    assert res.status_code == 401


def test_shortest_path_endpoint():
    client = TestClient(app)
    payload = {"source": "a", "target": "b"}
    res = client.post(
        "/analytics/shortest_path",
        json=payload,
        headers={"Authorization": f"Bearer {settings.UME_API_TOKEN}"},
    )
    assert res.status_code == 200
    assert res.json() == {"path": ["a", "b"]}


def test_constrained_path_endpoint():
    client = TestClient(app)
    payload = {"source": "a", "target": "b", "max_depth": 1}
    res = client.post(
        "/analytics/path",
        json=payload,
        headers={"Authorization": f"Bearer {settings.UME_API_TOKEN}"},
    )
    assert res.status_code == 200
    assert res.json() == {"path": ["a", "b"]}


def test_subgraph_endpoint():
    client = TestClient(app)
    payload = {"start": "a", "depth": 1}
    res = client.post(
        "/analytics/subgraph",
        json=payload,
        headers={"Authorization": f"Bearer {settings.UME_API_TOKEN}"},
    )
    assert res.status_code == 200
    assert set(res.json()["nodes"].keys()) == {"a", "b"}


def test_token_header_whitespace_and_case():
    client = TestClient(app)
    res = client.get(
        "/query",
        params={"cypher": "MATCH (n)"},
        headers={"Authorization": f"  bearer {settings.UME_API_TOKEN}  "},
    )
    assert res.status_code == 200


def test_malformed_authorization_header():
    client = TestClient(app)
    res = client.get(
        "/query",
        params={"cypher": "MATCH (n)"},
        headers={"Authorization": "Token bad"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Malformed Authorization header"


def test_metrics_endpoint():
    client = TestClient(app)
    res = client.get("/metrics")
    assert res.status_code == 200
