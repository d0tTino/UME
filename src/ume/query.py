"""Utilities for executing Cypher queries against a Neo4j database."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from neo4j import Driver, GraphDatabase


class Neo4jQueryEngine:
    """Simple wrapper around the Neo4j Bolt driver."""

    def __init__(self, driver: Driver) -> None:
        self._driver = driver

    @classmethod
    def from_credentials(cls, uri: str, user: str, password: str) -> "Neo4jQueryEngine":
        """Instantiate the engine from connection credentials."""
        driver = GraphDatabase.driver(uri, auth=(user, password))
        return cls(driver)

    def close(self) -> None:
        """Close the underlying driver connection."""
        self._driver.close()

    def execute_cypher(
        self, query: str, parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute an arbitrary Cypher query.

        Parameters
        ----------
        query: str
            The Cypher statement to execute.
        parameters: dict, optional
            Optional query parameters passed to Neo4j.

        Returns
        -------
        list[dict]
            A list of records represented as dictionaries.
        """
        with self._driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]


def build_events_query(
    *,
    tag: str | None = None,
    node_id: str | None = None,
    limit: int = 100,
) -> Tuple[str, Dict[str, Any]]:
    """Return Cypher and parameters to fetch events filtered by ``tag``.

    The returned statement matches nodes in the graph and optionally restricts
    results to those whose ``tags`` list contains ``tag`` or whose ``id``
    matches ``node_id``. Results are limited by ``limit``.
    """

    params: Dict[str, Any] = {"limit": limit}
    clauses: List[str] = []
    if tag is not None:
        params["tag"] = tag
        clauses.append("$tag IN n.tags")
    if node_id is not None:
        params["node_id"] = node_id
        clauses.append("n.id = $node_id")

    query = "MATCH (n)"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " RETURN n LIMIT $limit"
    return query, params
