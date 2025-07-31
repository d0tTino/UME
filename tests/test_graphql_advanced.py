from fastapi.testclient import TestClient
from ume.api import app, configure_graph
from ume import MockGraph


def setup_module(_):
    g = MockGraph()
    g.add_node("t1", {})
    g.add_node("doc1", {})
    g.add_node("doc2", {})
    g.add_node("e1", {})
    g.add_edge("t1", "doc1", "RELATES_TO")
    g.add_edge("t1", "doc2", "RELATES_TO")
    g.add_edge("doc1", "e1", "ASSOCIATED_WITH")
    configure_graph(g)


def test_documents_by_topic() -> None:
    client = TestClient(app)
    query = "{ documentsByTopic(topic: \"t1\") { id } }"
    res = client.post("/graphql", json={"query": query})
    assert res.status_code == 200
    ids = {d["id"] for d in res.json()["data"]["documentsByTopic"]}
    assert ids == {"doc1", "doc2"}


def test_documents_by_topic_filtered() -> None:
    client = TestClient(app)
    query = "{ documentsByTopic(topic: \"t1\", entity: \"e1\") { id } }"
    res = client.post("/graphql", json={"query": query})
    assert res.status_code == 200
    data = res.json()["data"]["documentsByTopic"]
    assert data == [{"id": "doc1"}]


def test_documents_by_topic_missing() -> None:
    client = TestClient(app)
    query = "{ documentsByTopic(topic: \"missing\") { id } }"
    res = client.post("/graphql", json={"query": query})
    assert res.status_code == 200
    assert res.json()["data"]["documentsByTopic"] == []

