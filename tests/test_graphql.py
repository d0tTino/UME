import pytest
from fastapi.testclient import TestClient

from ume import MockGraph
from ume.api import app, configure_graph


def _configure_permissions_graph() -> None:
    g = MockGraph()
    g.add_node("doc_visible", {"x": 1})
    g.add_node("doc_shared", {"z": 3})
    g.add_node("doc_other", {"y": 2})
    g.add_node("User.viewer", {})
    g.add_node("User.other", {})
    g.add_edge("doc_visible", "User.viewer", "OWNED_BY")
    g.add_edge("doc_shared", "User.viewer", "OWNED_BY")
    g.add_edge("doc_other", "User.other", "OWNED_BY")
    g.add_edge("doc_visible", "doc_shared", "RELATED")
    configure_graph(g)


@pytest.fixture(autouse=True)
def reset_graph() -> None:
    _configure_permissions_graph()


def test_query_nodes() -> None:
    client = TestClient(app)
    res = client.post(
        "/graphql",
        params={"user_id": "User.viewer"},
        json={"query": "{ nodes { id attributes } }"},
    )
    assert res.status_code == 200
    data = res.json()["data"]["nodes"]
    assert {"id": "doc_visible", "attributes": {"x": 1}} in data
    assert {"id": "doc_shared", "attributes": {"z": 3}} in data
    assert all(node["id"] != "doc_other" for node in data)


def test_query_edges() -> None:
    client = TestClient(app)
    res = client.post(
        "/graphql",
        params={"user_id": "User.viewer"},
        json={"query": "{ edges { source target label } }"},
    )
    assert res.status_code == 200
    data = res.json()["data"]["edges"]
    assert data == [{"source": "doc_visible", "target": "doc_shared", "label": "RELATED"}]


def test_create_node_mutation() -> None:
    client = TestClient(app)
    mutation = (
        "mutation($id: String!, $attrs: GenericScalar) {"
        "  createNode(id: $id, attributes: $attrs) { ok node { id attributes } }"
        "}"
    )
    res = client.post(
        "/graphql",
        params={"user_id": "User.viewer"},
        json={"query": mutation, "variables": {"id": "doc_new", "attrs": {"z": 3}}},
    )
    assert res.status_code == 200
    assert res.json()["data"]["createNode"]["ok"] is True
    assert app.state.graph.get_node("doc_new") == {"z": 3}


def _edge_exists(source: str, target: str, label: str) -> bool:
    for s, t, lbl, _ in app.state.graph.get_all_edges():
        if s == source and t == target and lbl == label:
            return True
    return False


def test_create_edge_mutation() -> None:
    client = TestClient(app)
    mutation = (
        "mutation($s: String!, $t: String!, $lbl: String!) {"
        "  createEdge(source: $s, target: $t, label: $lbl) { ok }"
        "}"
    )
    res = client.post(
        "/graphql",
        params={"user_id": "User.viewer"},
        json={
            "query": mutation,
            "variables": {"s": "doc_shared", "t": "doc_visible", "lbl": "LINKS"},
        },
    )
    assert res.status_code == 200
    assert res.json()["data"]["createEdge"]["ok"] is True
    assert _edge_exists("doc_shared", "doc_visible", "LINKS")


def test_edges_for_node() -> None:
    client = TestClient(app)
    query = "{ node(id: \"doc_visible\") { edges { source target label } } }"
    res = client.post(
        "/graphql",
        params={"user_id": "User.viewer"},
        json={"query": query},
    )
    assert res.status_code == 200
    edges = res.json()["data"]["node"]["edges"]
    assert edges == [{"source": "doc_visible", "target": "doc_shared", "label": "RELATED"}]


def test_path_query() -> None:
    client = TestClient(app)
    query = "{ path(source: \"doc_visible\", target: \"doc_shared\") }"
    res = client.post(
        "/graphql",
        params={"user_id": "User.viewer"},
        json={"query": query},
    )
    assert res.status_code == 200
    assert res.json()["data"]["path"] == ["doc_visible", "doc_shared"]


def test_unauthorized_user_cannot_read_inaccessible_node() -> None:
    client = TestClient(app)
    query = "{ node(id: \"doc_visible\") { id attributes } }"
    res = client.post(
        "/graphql",
        params={"user_id": "User.other"},
        json={"query": query},
    )
    assert res.status_code == 200
    assert res.json()["data"]["node"] is None


def test_unauthorized_user_cannot_mutate_without_editor() -> None:
    client = TestClient(app)
    mutation = (
        "mutation {"
        "  createEdge(source: \"doc_visible\", target: \"doc_shared\", label: \"FAIL\") { ok }"
        "}"
    )
    res = client.post(
        "/graphql",
        params={"user_id": "User.other"},
        json={"query": mutation},
    )
    body = res.json()
    assert "errors" in body
    assert any("Editor permission required" in err["message"] for err in body["errors"])
    assert not _edge_exists("doc_visible", "doc_shared", "FAIL")
