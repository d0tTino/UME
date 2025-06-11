"""Utilities for executing Cypher queries against a Neo4j database."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase, Driver


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
