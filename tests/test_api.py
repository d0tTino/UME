from fastapi.testclient import TestClient

from ume.api import app
from ume import MockGraph


def setup_module(_):
    # configure app state for tests
    app.state.query_engine = type(
        "QE",
        (),
        {"execute_cypher": lambda self, q: [{"q": q}]}
    )()
    g = MockGraph()
    g.add_node("a", {})
    g.add_node("b", {})
    g.add_edge("a", "b", "L")
    app.state.graph = g


def test_run_query_authorized():
    client = TestClient(app)
    res = client.get("/query", params={"cypher": "MATCH (n) RETURN n"}, headers={"Authorization": "Bearer secret-token"})
    assert res.status_code == 200
    assert res.json() == [{"q": "MATCH (n) RETURN n"}]


def test_run_query_unauthorized():
    client = TestClient(app)
    res = client.get("/query", params={"cypher": "MATCH (n)"})
    assert res.status_code == 401


def test_shortest_path_endpoint():
    client = TestClient(app)
    payload = {"source": "a", "target": "b"}
    res = client.post("/analytics/shortest_path", json=payload, headers={"Authorization": "Bearer secret-token"})
    assert res.status_code == 200
    assert res.json() == {"path": ["a", "b"]}
