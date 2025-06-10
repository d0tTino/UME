import pytest

from ume.neo4j_graph import Neo4jGraph
from ume.processing import ProcessingError


class DummyResult:
    def __init__(self, record=None):
        self._record = record

    def single(self):
        return self._record


class DummySession:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def run(self, query, parameters=None):
        self.calls.append((query, parameters))
        return self.results.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


class DummyDriver:
    def __init__(self, results):
        self.session_obj = DummySession(results)

    def session(self):
        return self.session_obj

    def close(self):
        pass


def test_node_and_edge_crud():
    results = [
        DummyResult({"cnt": 0}),  # check node1
        DummyResult(None),  # create node1
        DummyResult({"cnt": 0}),  # check node2
        DummyResult(None),  # create node2
        DummyResult({"scnt": 1, "tcnt": 1}),  # check nodes exist for edge
        DummyResult({"cnt": 0}),  # check existing edge
        DummyResult(None),  # create edge
        DummyResult({"cnt": 1}),  # delete edge
    ]
    driver = DummyDriver(results)
    graph = Neo4jGraph("bolt://localhost:7687", "neo4j", "pass", driver=driver)

    graph.add_node("n1", {})
    graph.add_node("n2", {})
    graph.add_edge("n1", "n2", "REL")
    graph.delete_edge("n1", "n2", "REL")

    assert len(driver.session_obj.calls) == 8


def test_add_node_duplicate_raises():
    driver = DummyDriver([DummyResult({"cnt": 1})])
    graph = Neo4jGraph("bolt://localhost:7687", "neo4j", "pass", driver=driver)

    with pytest.raises(ProcessingError):
        graph.add_node("dup", {})


def test_gds_methods_issue_queries():
    results = [[], [], [], [], [], []]
    driver = DummyDriver(results)
    graph = Neo4jGraph(
        "bolt://localhost:7687",
        "neo4j",
        "pass",
        driver=driver,
        use_gds=True,
    )

    graph.pagerank_centrality()
    graph.betweenness_centrality()
    graph.community_detection()
    graph.node_similarity()
    graph.temporal_community_detection(5)
    graph.time_varying_centrality(5)

    queries = [q for q, _ in driver.session_obj.calls]
    assert "gds.pageRank.stream" in queries[0]
    assert "gds.betweenness.stream" in queries[1]
    assert "gds.louvain.stream" in queries[2]
    assert "gds.nodeSimilarity.stream" in queries[3]
    assert "gds.beta.temporalClustering.stream" in queries[4]
    assert "gds.beta.timeWeightedPageRank.stream" in queries[5]
