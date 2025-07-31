from fastapi.testclient import TestClient
from ume.api import app, configure_graph
from ume import MockGraph


def setup_module(_):
    g = MockGraph()
    g.add_node("a", {"x": 1})
    g.add_node("b", {"y": 2})
    g.add_edge("a", "b", "ab")
    configure_graph(g)


def test_query_nodes() -> None:
    client = TestClient(app)
    res = client.post("/graphql", json={"query": "{ nodes { id attributes } }"})
    assert res.status_code == 200
    data = res.json()["data"]["nodes"]
    assert {"id": "a", "attributes": {"x": 1}} in data
    assert {"id": "b", "attributes": {"y": 2}} in data


def test_query_edges() -> None:
    client = TestClient(app)
    res = client.post("/graphql", json={"query": "{ edges { source target label } }"})
    assert res.status_code == 200
    data = res.json()["data"]["edges"]
    assert {"source": "a", "target": "b", "label": "ab"} in data


def test_create_node_mutation() -> None:
    client = TestClient(app)
    mutation = (
        "mutation($id: String!, $attrs: GenericScalar) {"
        "  createNode(id: $id, attributes: $attrs) { ok node { id attributes } }"
        "}"
    )
    res = client.post(
        "/graphql",
        json={"query": mutation, "variables": {"id": "c", "attrs": {"z": 3}}},
    )
    assert res.status_code == 200
    assert res.json()["data"]["createNode"]["ok"] is True
    assert app.state.graph.get_node("c") == {"z": 3}


def test_create_edge_mutation() -> None:
    client = TestClient(app)
    mutation = (
        "mutation($s: String!, $t: String!, $lbl: String!) {"
        "  createEdge(source: $s, target: $t, label: $lbl) { ok }"
        "}"
    )
    res = client.post(
        "/graphql",
        json={"query": mutation, "variables": {"s": "b", "t": "a", "lbl": "ba"}},
    )
    assert res.status_code == 200
    assert res.json()["data"]["createEdge"]["ok"] is True
    assert ("b", "a", "ba") in app.state.graph.get_all_edges()


def test_edges_for_node() -> None:
    client = TestClient(app)
    query = "{ node(id: \"a\") { edges { source target label } } }"
    res = client.post("/graphql", json={"query": query})
    assert res.status_code == 200
    edges = res.json()["data"]["node"]["edges"]
    assert edges == [{"source": "a", "target": "b", "label": "ab"}]


def test_path_query() -> None:
    client = TestClient(app)
    query = "{ path(source: \"a\", target: \"b\") }"
    res = client.post("/graphql", json={"query": query})
    assert res.status_code == 200
    assert res.json()["data"]["path"] == ["a", "b"]
