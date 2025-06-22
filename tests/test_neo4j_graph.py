import pytest

from typing import cast

from neo4j import Driver
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
    graph = Neo4jGraph(
        "bolt://localhost:7687",
        "neo4j",
        "pass",
        driver=cast(Driver, driver),
    )

    graph.add_node("n1", {})
    graph.add_node("n2", {})
    graph.add_edge("n1", "n2", "RELATES_TO")
    graph.delete_edge("n1", "n2", "RELATES_TO")

    assert len(driver.session_obj.calls) == 8


def test_add_edge_parameterized_label():
    label = "RELATES_TO"
    results = [
        DummyResult({"scnt": 1, "tcnt": 1}),  # check nodes exist
        DummyResult({"cnt": 0}),  # check existing edge
        DummyResult(None),  # create edge
    ]
    driver = DummyDriver(results)
    graph = Neo4jGraph(
        "bolt://localhost:7687",
        "neo4j",
        "pass",
        driver=cast(Driver, driver),
    )

    graph.add_edge("s1", "t1", label)

    # Second call checks for existing edge using parameterized label
    check_query, check_params = driver.session_obj.calls[1]
    create_query, create_params = driver.session_obj.calls[2]
    assert label in check_query
    assert label in create_query
    assert check_params == {"src": "s1", "tgt": "t1"}
    assert create_params["src"] == "s1"
    assert create_params["tgt"] == "t1"
    assert isinstance(create_params.get("ts"), int)


def test_add_node_duplicate_raises():
    driver = DummyDriver([DummyResult({"cnt": 1})])
    graph = Neo4jGraph(
        "bolt://localhost:7687",
        "neo4j",
        "pass",
        driver=cast(Driver, driver),
    )

    with pytest.raises(ProcessingError):
        graph.add_node("dup", {})


def test_gds_methods_issue_queries() -> None:
    results: list[list] = [[], [], [], [], [], [], []]
    driver = DummyDriver(results)
    graph = Neo4jGraph(
        "bolt://localhost:7687",
        "neo4j",
        "pass",
        driver=cast(Driver, driver),
        use_gds=True,
    )

    graph.pagerank_centrality()
    graph.betweenness_centrality()
    graph.community_detection()
    graph.node_similarity()
    graph.graph_similarity(graph)
    graph.temporal_community_detection(5)
    graph.time_varying_centrality(5)

    queries = [q for q, _ in driver.session_obj.calls]
    assert "gds.pageRank.stream" in queries[0]
    assert "gds.betweenness.stream" in queries[1]
    assert "gds.louvain.stream" in queries[2]
    assert "gds.nodeSimilarity.stream" in queries[3]
    assert "gds.beta.temporalClustering.stream" in queries[-2]
    assert "gds.beta.timeWeightedPageRank.stream" in queries[-1]
    assert len(queries) >= 7


def test_find_connected_nodes_query_filters_redacted_edges_unlabeled() -> None:
    results = [
        DummyResult({"cnt": 1}),
        [],
    ]
    driver = DummyDriver(results)
    graph = Neo4jGraph(
        "bolt://localhost:7687",
        "neo4j",
        "pass",
        driver=cast(Driver, driver),
    )

    graph.find_connected_nodes("n1")

    query, params = driver.session_obj.calls[1]
    assert "coalesce(r.redacted, false) = false" in query
    assert params == {"node_id": "n1"}


def test_find_connected_nodes_query_filters_redacted_edges_with_label() -> None:
    results = [
        DummyResult({"cnt": 1}),
        [],
    ]
    driver = DummyDriver(results)
    graph = Neo4jGraph(
        "bolt://localhost:7687",
        "neo4j",
        "pass",
        driver=cast(Driver, driver),
    )

    graph.find_connected_nodes("n1", edge_label="REL")

    query, params = driver.session_obj.calls[1]
    assert "coalesce(r.redacted, false) = false" in query
    assert "coalesce(m.redacted, false) = false" in query
    assert "`REL`" in query
    assert params == {"node_id": "n1"}


def test_purge_old_records_issues_queries() -> None:
    results = [
        DummyResult(None),
        DummyResult(None),
    ]
    driver = DummyDriver(results)
    graph = Neo4jGraph(
        "bolt://localhost:7687",
        "neo4j",
        "pass",
        driver=cast(Driver, driver),
    )

    graph.purge_old_records(3600)

    delete_edges_query, delete_edges_params = driver.session_obj.calls[0]
    delete_nodes_query, delete_nodes_params = driver.session_obj.calls[1]
    assert "r.created_at < $cutoff" in delete_edges_query
    assert "n.created_at < $cutoff" in delete_nodes_query
    assert delete_edges_params == delete_nodes_params
    assert isinstance(delete_edges_params["cutoff"], int)
