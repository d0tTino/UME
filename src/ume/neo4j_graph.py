# src/ume/neo4j_graph.py
"""Neo4j-backed implementation of :class:`~ume.graph_adapter.IGraphAdapter`."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, cast, TYPE_CHECKING
import time

from neo4j import GraphDatabase, Driver
from .schema_manager import DEFAULT_SCHEMA_MANAGER
from .processing import DEFAULT_VERSION

from .graph_adapter import IGraphAdapter
from .processing import ProcessingError
from .graph_algorithms import GraphAlgorithmsMixin
from .replay import replay_from_ledger

if TYPE_CHECKING:  # pragma: no cover - for type hints only
    from .event_ledger import EventLedger


class Neo4jGraph(GraphAlgorithmsMixin, IGraphAdapter):
    """Graph adapter using the Neo4j Bolt driver."""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        driver: Optional[Driver] = None,
        *,
        use_gds: bool = False,
    ) -> None:
        self._driver = driver or GraphDatabase.driver(uri, auth=(user, password))
        self._use_gds = use_gds

    def close(self) -> None:
        self._driver.close()

    # ---- Node methods -------------------------------------------------
    def add_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (n {id: $node_id}) RETURN count(n) AS cnt",
                {"node_id": node_id},
            )
            rec = result.single()
            assert rec is not None
            if rec["cnt"] > 0:
                raise ProcessingError(f"Node '{node_id}' already exists.")
            session.run(
                "CREATE (n {id: $node_id, created_at:$ts}) SET n += $attrs",
                {"node_id": node_id, "attrs": attributes, "ts": int(time.time())},
            )

    def update_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (n {id: $node_id}) RETURN count(n) AS cnt",
                {"node_id": node_id},
            )
            rec = result.single()
            assert rec is not None
            if rec["cnt"] == 0:
                raise ProcessingError(f"Node '{node_id}' not found for update.")
            session.run(
                "MATCH (n {id: $node_id}) SET n += $attrs",
                {"node_id": node_id, "attrs": attributes},
            )

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (n {id: $node_id}) WHERE coalesce(n.redacted, false) = false RETURN properties(n) AS props",
                {"node_id": node_id},
            )
            rec = result.single()
            if rec is None:
                return None
            return cast(Dict[str, Any], rec["props"])

    def node_exists(self, node_id: str) -> bool:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (n {id: $node_id}) WHERE coalesce(n.redacted, false) = false RETURN count(n) AS cnt",
                {"node_id": node_id},
            )
            rec = result.single()
            assert rec is not None
            cnt = cast(int, rec["cnt"])
            return cnt > 0

    def dump(self) -> Dict[str, Any]:
        nodes: Dict[str, Any] = {}
        with self._driver.session() as session:
            for record in session.run(
                "MATCH (n) WHERE coalesce(n.redacted, false) = false RETURN n.id AS id, properties(n) AS props"
            ):
                nodes[record["id"]] = record["props"]
        edges = self.get_all_edges()
        return {"nodes": nodes, "edges": edges}

    def clear(self) -> None:
        with self._driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def get_all_node_ids(self) -> List[str]:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (n) WHERE coalesce(n.redacted, false) = false RETURN n.id AS id"
            )
            return [record["id"] for record in result]

    def find_connected_nodes(
        self, node_id: str, edge_label: Optional[str] = None
    ) -> List[str]:
        if not self.node_exists(node_id):
            raise ProcessingError(f"Node '{node_id}' not found.")
        with self._driver.session() as session:
            if edge_label:
                escaped_label = edge_label.replace("`", "``")
                query = (
                    f"MATCH (n {{id: $node_id}})-[r:`{escaped_label}`]->(m) "
                    "WHERE coalesce(r.redacted, false) = false "
                    "AND coalesce(m.redacted, false) = false RETURN m.id AS id"
                )
                result = session.run(query, {"node_id": node_id})
            else:
                query = (
                    "MATCH (n {id: $node_id})-[r]->(m) "
                    "WHERE coalesce(r.redacted, false) = false "
                    "AND coalesce(m.redacted, false) = false RETURN m.id AS id"
                )
                result = session.run(query, {"node_id": node_id})
            return [record["id"] for record in result]

    # ---- Edge methods -------------------------------------------------
    def add_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        schema = DEFAULT_SCHEMA_MANAGER.get_schema(DEFAULT_VERSION)
        schema.validate_edge_label(label)
        escaped_label = label.replace("`", "``")
        with self._driver.session() as session:
            result = session.run(
                "MATCH (s {id: $src}), (t {id: $tgt}) RETURN count(s) AS scnt, count(t) AS tcnt",
                {"src": source_node_id, "tgt": target_node_id},
            )
            rec = result.single()
            assert rec is not None
            if rec["scnt"] == 0 or rec["tcnt"] == 0:
                raise ProcessingError(
                    f"Both source node '{source_node_id}' and target node '{target_node_id}' must exist to add an edge."
                )
            result = session.run(
                f"MATCH (s {{id: $src}})-[r:`{escaped_label}`]->(t {{id: $tgt}}) RETURN count(r) AS cnt",
                {"src": source_node_id, "tgt": target_node_id},
            )
            rec = result.single()
            assert rec is not None
            if rec["cnt"] > 0:
                raise ProcessingError(
                    f"Edge ({source_node_id}, {target_node_id}, {label}) already exists."
                )
            session.run(
                f"MATCH (s {{id: $src}}), (t {{id: $tgt}}) CREATE (s)-[:`{escaped_label}` {{redacted:false, created_at:$ts}}]->(t)",
                {"src": source_node_id, "tgt": target_node_id, "ts": int(time.time())},
            )

    def get_all_edges(self) -> List[tuple[str, str, str]]:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (s)-[r]->(t) "
                "WHERE coalesce(r.redacted, false) = false "
                "AND coalesce(s.redacted, false) = false "
                "AND coalesce(t.redacted, false) = false "
                "RETURN s.id AS src, t.id AS tgt, type(r) AS label"
            )
            return [(rec["src"], rec["tgt"], rec["label"]) for rec in result]

    def delete_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        schema = DEFAULT_SCHEMA_MANAGER.get_schema(DEFAULT_VERSION)
        schema.validate_edge_label(label)
        escaped_label = label.replace("`", "``")
        with self._driver.session() as session:
            result = session.run(
                f"MATCH (s {{id: $src}})-[r:`{escaped_label}`]->(t {{id: $tgt}}) DELETE r RETURN count(r) AS cnt",
                {"src": source_node_id, "tgt": target_node_id},
            )
            rec = result.single()
            assert rec is not None
            if rec["cnt"] == 0:
                edge_tuple = (source_node_id, target_node_id, label)
                raise ProcessingError(
                    f"Edge {edge_tuple} does not exist and cannot be deleted."
                )

    def redact_node(self, node_id: str) -> None:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (n {id: $node_id}) SET n.redacted = true RETURN count(n) AS cnt",
                {"node_id": node_id},
            )
            rec = result.single()
            assert rec is not None
            if rec["cnt"] == 0:
                raise ProcessingError(f"Node '{node_id}' not found to redact.")

    def redact_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        schema = DEFAULT_SCHEMA_MANAGER.get_schema(DEFAULT_VERSION)
        schema.validate_edge_label(label)
        escaped_label = label.replace("`", "``")
        with self._driver.session() as session:
            result = session.run(
                f"MATCH (s {{id: $src}})-[r:`{escaped_label}`]->(t {{id: $tgt}}) SET r.redacted = true RETURN count(r) AS cnt",
                {"src": source_node_id, "tgt": target_node_id},
            )
            rec = result.single()
            assert rec is not None
            if rec["cnt"] == 0:
                edge_tuple = (source_node_id, target_node_id, label)
                raise ProcessingError(
                    f"Edge {edge_tuple} does not exist and cannot be redacted."
                )

    def purge_old_records(self, max_age_seconds: int) -> None:
        """Delete nodes and edges older than ``max_age_seconds``."""
        cutoff = int(time.time()) - max_age_seconds
        with self._driver.session() as session:
            session.run(
                "MATCH ()-[r]->() WHERE r.created_at < $cutoff DELETE r",
                {"cutoff": cutoff},
            )
            session.run(
                "MATCH (n) WHERE n.created_at < $cutoff DETACH DELETE n",
                {"cutoff": cutoff},
            )

    # ---- Graph Data Science helpers --------------------------------------------
    def _ensure_gds_enabled(self) -> None:
        if not getattr(self, "_use_gds", False):
            raise NotImplementedError("GDS integration not enabled")

    def pagerank_centrality(self) -> Dict[str, float]:
        self._ensure_gds_enabled()
        with self._driver.session() as session:
            result = session.run(
                "CALL gds.pageRank.stream({nodeProjection:'*', relationshipProjection:'*'}) "
                "YIELD nodeId, score RETURN gds.util.asNode(nodeId).id AS id, score"
            )
            return {rec["id"]: rec["score"] for rec in result}

    def betweenness_centrality(self) -> Dict[str, float]:
        self._ensure_gds_enabled()
        with self._driver.session() as session:
            result = session.run(
                "CALL gds.betweenness.stream({nodeProjection:'*', relationshipProjection:'*'}) "
                "YIELD nodeId, score RETURN gds.util.asNode(nodeId).id AS id, score"
            )
            return {rec["id"]: rec["score"] for rec in result}

    def community_detection(self) -> List[set[str]]:
        self._ensure_gds_enabled()
        with self._driver.session() as session:
            result = session.run(
                "CALL gds.louvain.stream({nodeProjection:'*', relationshipProjection:'*'}) "
                "YIELD nodeId, communityId RETURN gds.util.asNode(nodeId).id AS id, communityId"
            )
            communities: Dict[int, set[str]] = {}
            for rec in result:
                cid = rec["communityId"]
                communities.setdefault(cid, set()).add(rec["id"])
            return list(communities.values())

    def node_similarity(self) -> List[tuple[str, str, float]]:
        self._ensure_gds_enabled()
        with self._driver.session() as session:
            result = session.run(
                "CALL gds.nodeSimilarity.stream({nodeProjection:'*', relationshipProjection:'*'}) "
                "YIELD node1, node2, similarity "
                "RETURN gds.util.asNode(node1).id AS source, gds.util.asNode(node2).id AS target, similarity"
            )
            return [(rec["source"], rec["target"], rec["similarity"]) for rec in result]

    def graph_similarity(self, other: "Neo4jGraph") -> float:
        """Compute a Jaccard similarity between this graph and ``other``."""
        self._ensure_gds_enabled()
        if self._driver is not other._driver:
            raise NotImplementedError("Graphs must share the same driver")
        edges1 = set(self.get_all_edges())
        edges2 = edges1 if other is self else set(other.get_all_edges())
        if not edges1 and not edges2:
            return 1.0
        return len(edges1 & edges2) / len(edges1 | edges2)

    def temporal_community_detection(self, window: int) -> List[set[str]]:
        """Detect communities over a moving time window."""
        self._ensure_gds_enabled()
        with self._driver.session() as session:
            result = session.run(
                "CALL gds.beta.temporalClustering.stream({"
                "nodeProjection:'*', relationshipProjection:'*', windowSize:$window}) "
                "YIELD nodeId, communityId RETURN gds.util.asNode(nodeId).id AS id, communityId",
                {"window": window},
            )
            communities: Dict[int, set[str]] = {}
            for rec in result:
                cid = rec["communityId"]
                communities.setdefault(cid, set()).add(rec["id"])
            return list(communities.values())

    def time_varying_centrality(self, window: int) -> Dict[str, float]:
        """Compute centrality scores within a moving time window."""
        self._ensure_gds_enabled()
        with self._driver.session() as session:
            result = session.run(
                "CALL gds.beta.timeWeightedPageRank.stream({"
                "nodeProjection:'*', relationshipProjection:'*', windowSize:$window}) "
                "YIELD nodeId, score RETURN gds.util.asNode(nodeId).id AS id, score",
                {"window": window},
            )
            return {rec["id"]: rec["score"] for rec in result}

    def replay_from_ledger(
        self,
        ledger: "EventLedger",
        start_offset: int = 0,
        end_offset: int | None = None,
        *,
        end_timestamp: int | None = None,
    ) -> int:
        """Delegate to :func:`ume.replay.replay_from_ledger`."""
        return replay_from_ledger(
            self,
            ledger,
            start_offset=start_offset,
            end_offset=end_offset,
            end_timestamp=end_timestamp,
        )
