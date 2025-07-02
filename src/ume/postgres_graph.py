"""PostgreSQL-backed graph adapter."""
from __future__ import annotations

import importlib
import json
import time
from typing import Any, Dict, List, Optional, Tuple, cast

from .graph_adapter import IGraphAdapter
from .processing import ProcessingError
from .graph_algorithms import GraphAlgorithmsMixin
from .audit import log_audit_entry
from .config import settings

_spec = importlib.util.find_spec("psycopg")
psycopg = importlib.import_module("psycopg") if _spec is not None else None


class PostgresGraph(GraphAlgorithmsMixin, IGraphAdapter):
    """Graph adapter using PostgreSQL via psycopg."""

    def __init__(self, dsn: str | None = None) -> None:
        if psycopg is None:
            raise ImportError("psycopg is required for PostgresGraph")
        self._dsn = dsn or settings.UME_DB_PATH
        self._conn = psycopg.connect(self._dsn, autocommit=True)
        self._create_tables()

    def _create_tables(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    attributes JSONB,
                    redacted BOOLEAN DEFAULT FALSE,
                    created_at BIGINT DEFAULT EXTRACT(EPOCH FROM NOW())
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS edges (
                    source TEXT,
                    target TEXT,
                    label TEXT,
                    redacted BOOLEAN DEFAULT FALSE,
                    created_at BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()),
                    PRIMARY KEY (source, target, label)
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target)")

    # ---- Resource management -------------------------------------------------
    def close(self) -> None:
        self._conn.close()

    # ---- Node methods -------------------------------------------------------
    def add_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM nodes WHERE id=%s AND redacted=false",
                (node_id,),
            )
            if cur.fetchone() is not None:
                raise ProcessingError(f"Node '{node_id}' already exists.")
            cur.execute(
                "INSERT INTO nodes(id, attributes, created_at) VALUES(%s, %s, %s)",
                (node_id, json.dumps(attributes), int(time.time())),
            )

    def update_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT attributes FROM nodes WHERE id=%s AND redacted=false",
                (node_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise ProcessingError(f"Node '{node_id}' not found for update.")
            data = json.loads(row[0])
            data.update(attributes)
            cur.execute(
                "UPDATE nodes SET attributes=%s WHERE id=%s",
                (json.dumps(data), node_id),
            )

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT attributes FROM nodes WHERE id=%s AND redacted=false",
                (node_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return cast(Dict[str, Any], json.loads(row[0]))

    def node_exists(self, node_id: str) -> bool:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM nodes WHERE id=%s AND redacted=false",
                (node_id,),
            )
            return cur.fetchone() is not None

    def get_all_node_ids(self) -> List[str]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT id FROM nodes WHERE redacted=false")
            return [row[0] for row in cur.fetchall()]

    def dump(self) -> Dict[str, Any]:
        nodes: Dict[str, Any] = {}
        with self._conn.cursor() as cur:
            cur.execute("SELECT id, attributes FROM nodes WHERE redacted=false")
            for nid, attrs in cur.fetchall():
                nodes[nid] = json.loads(attrs)
        edges = self.get_all_edges()
        return {"nodes": nodes, "edges": edges}

    def clear(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute("TRUNCATE edges")
            cur.execute("TRUNCATE nodes")

    # ---- Edge methods -------------------------------------------------------
    def add_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        if not self.node_exists(source_node_id) or not self.node_exists(target_node_id):
            raise ProcessingError(
                f"Both source node '{source_node_id}' and target node '{target_node_id}' must exist to add an edge."
            )
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM edges WHERE source=%s AND target=%s AND label=%s",
                (source_node_id, target_node_id, label),
            )
            if cur.fetchone() is not None:
                raise ProcessingError(
                    f"Edge ({source_node_id}, {target_node_id}, {label}) already exists."
                )
            cur.execute(
                "INSERT INTO edges(source, target, label, created_at) VALUES(%s, %s, %s, %s)",
                (source_node_id, target_node_id, label, int(time.time())),
            )

    def get_all_edges(self) -> List[Tuple[str, str, str]]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.source, e.target, e.label
                FROM edges e
                JOIN nodes s ON e.source = s.id
                JOIN nodes t ON e.target = t.id
                WHERE e.redacted=false AND s.redacted=false AND t.redacted=false
                """
            )
            return [(row[0], row[1], row[2]) for row in cur.fetchall()]

    def delete_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "DELETE FROM edges WHERE source=%s AND target=%s AND label=%s",
                (source_node_id, target_node_id, label),
            )
            if cur.rowcount == 0:
                edge_tuple = (source_node_id, target_node_id, label)
                raise ProcessingError(
                    f"Edge {edge_tuple} does not exist and cannot be deleted."
                )

    def find_connected_nodes(self, node_id: str, edge_label: Optional[str] = None) -> List[str]:
        if not self.node_exists(node_id):
            raise ProcessingError(f"Node '{node_id}' not found.")
        with self._conn.cursor() as cur:
            if edge_label:
                cur.execute(
                    """
                    SELECT e.target FROM edges e
                    JOIN nodes s ON e.source = s.id
                    JOIN nodes t ON e.target = t.id
                    WHERE e.source=%s AND e.label=%s
                      AND e.redacted=false AND s.redacted=false AND t.redacted=false
                    """,
                    (node_id, edge_label),
                )
            else:
                cur.execute(
                    """
                    SELECT e.target FROM edges e
                    JOIN nodes s ON e.source = s.id
                    JOIN nodes t ON e.target = t.id
                    WHERE e.source=%s AND e.redacted=false AND s.redacted=false AND t.redacted=false
                    """,
                    (node_id,),
                )
            return [row[0] for row in cur.fetchall()]

    # ---- Redaction ----------------------------------------------------------
    def redact_node(self, node_id: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE nodes SET redacted=true WHERE id=%s",
                (node_id,),
            )
            if cur.rowcount == 0:
                raise ProcessingError(f"Node '{node_id}' not found to redact.")
        log_audit_entry(settings.UME_AGENT_ID, f"redact_node {node_id}")

    def redact_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE edges SET redacted=true WHERE source=%s AND target=%s AND label=%s",
                (source_node_id, target_node_id, label),
            )
            if cur.rowcount == 0:
                edge_tuple = (source_node_id, target_node_id, label)
                raise ProcessingError(
                    f"Edge {edge_tuple} does not exist and cannot be redacted."
                )
        log_audit_entry(settings.UME_AGENT_ID, f"redact_edge {source_node_id} {target_node_id} {label}")

    # ---- Misc utilities -----------------------------------------------------
    def purge_old_records(self, max_age_seconds: int) -> None:
        cutoff = int(time.time()) - max_age_seconds - 1
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM edges WHERE created_at < %s", (cutoff,))
            cur.execute(
                "DELETE FROM edges WHERE source IN (SELECT id FROM nodes WHERE created_at < %s)"
                " OR target IN (SELECT id FROM nodes WHERE created_at < %s)",
                (cutoff, cutoff),
            )
            cur.execute("DELETE FROM nodes WHERE created_at < %s", (cutoff,))


