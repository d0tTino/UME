from fastapi.testclient import TestClient
from ume.api import app, configure_graph
from ume import MockGraph


def setup_module(_):
    g = MockGraph()
    g.add_node("a", {"x": 1})
    configure_graph(g)


def test_query_nodes() -> None:
    client = TestClient(app)
    res = client.post("/graphql", json={"query": "{ nodes { id attributes } }"})
    assert res.status_code == 200
    data = res.json()["data"]["nodes"]
    assert {"id": "a", "attributes": {"x": 1}} in data


def test_create_node_mutation() -> None:
    client = TestClient(app)
    mutation = (
        "mutation($id: String!, $attrs: GenericScalar) {"
        "  createNode(id: $id, attributes: $attrs) { ok node { id attributes } }"
        "}"
    )
    res = client.post(
        "/graphql",
        json={"query": mutation, "variables": {"id": "b", "attrs": {"y": 2}}},
    )
    assert res.status_code == 200
    assert res.json()["data"]["createNode"]["ok"] is True
    assert app.state.graph.get_node("b") == {"y": 2}
