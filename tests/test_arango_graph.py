import pytest

from ume.arango_graph import ArangoGraph
from ume.processing import ProcessingError


class DummyCollection:
    def __init__(self):
        self.docs = {}
        self.calls = []

    def has(self, key):
        self.calls.append(("has", key))
        return key in self.docs

    def insert(self, doc):
        self.calls.append(("insert", doc))
        self.docs[doc["_key"]] = doc

    def update(self, doc):
        self.calls.append(("update", doc))
        self.docs[doc["_key"]] = doc

    def get(self, key):
        self.calls.append(("get", key))
        return self.docs.get(key)

    def delete(self, doc_or_key):
        key = doc_or_key if isinstance(doc_or_key, str) else doc_or_key["_key"]
        self.calls.append(("delete", key))
        if key not in self.docs:
            raise Exception("not found")
        del self.docs[key]

    def find(self, filters):
        self.calls.append(("find", filters))
        for doc in list(self.docs.values()):
            if all(doc.get(k) == v for k, v in filters.items()):
                yield doc

    def all(self):
        self.calls.append(("all", None))
        return list(self.docs.values())

    def truncate(self):
        self.calls.append(("truncate", None))
        self.docs.clear()


class DummyDatabase:
    def __init__(self):
        self.collections = {
            "nodes": DummyCollection(),
            "edges": DummyCollection(),
        }

    def has_collection(self, name):
        return name in self.collections

    def create_collection(self, name):
        self.collections[name] = DummyCollection()

    def collection(self, name):
        return self.collections[name]


def test_node_and_edge_crud():
    db = DummyDatabase()
    graph = ArangoGraph("http://localhost:8529", "root", "pass", db=db)
    graph.add_node("n1", {"v": 1})
    graph.add_node("n2", {})
    assert graph.get_node("n1")["v"] == 1
    graph.update_node("n1", {"v": 2})
    assert graph.get_node("n1")["v"] == 2
    graph.add_edge("n1", "n2", "R")
    assert ("n1", "n2", "R", {}) in graph.get_all_edges()
    graph.delete_edge("n1", "n2", "R")
    assert graph.get_all_edges() == []


def test_add_node_duplicate_raises():
    db = DummyDatabase()
    graph = ArangoGraph("http://localhost:8529", "root", "pass", db=db)
    graph.add_node("dup", {})
    with pytest.raises(ProcessingError):
        graph.add_node("dup", {})


def test_find_connected_nodes_filters_label():
    db = DummyDatabase()
    graph = ArangoGraph("http://localhost:8529", "root", "pass", db=db)
    graph.add_node("a", {})
    graph.add_node("b", {})
    graph.add_node("c", {})
    graph.add_edge("a", "b", "L1")
    graph.add_edge("a", "c", "L2")
    assert graph.find_connected_nodes("a", edge_label="L1") == ["b"]
