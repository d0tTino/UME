"""PostgreSQL-backed graph adapter."""
from __future__ import annotations

import importlib
import json
import time
from typing import Any, Dict, List, Optional, Tuple, cast, TYPE_CHECKING

from .graph_adapter import IGraphAdapter
from .processing import ProcessingError
from .graph_algorithms import GraphAlgorithmsMixin
from .audit import log_audit_entry
from .config import settings
from .replay import replay_from_ledger
from .graph_schema import DEFAULT_SCHEMA

if TYPE_CHECKING:  # pragma: no cover - for type hints only
    from .event_ledger import EventLedger

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
                    attributes JSONB DEFAULT '{}'::jsonb,
                    redacted BOOLEAN DEFAULT FALSE,
                    created_at BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()),
                    PRIMARY KEY (source, target, label)
                )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target)")

        # Ensure the attributes column exists and uses JSONB for legacy databases.
        cur.execute(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'edges' AND column_name = 'attributes'
            """
        )
        column_info = cur.fetchone()
        if column_info is None:
            cur.execute(
                "ALTER TABLE edges ADD COLUMN attributes JSONB DEFAULT '{}'::jsonb"
            )
        elif column_info[0] != "jsonb":
            cur.execute(
                """
                ALTER TABLE edges
                ALTER COLUMN attributes TYPE JSONB USING (
                    CASE
                        WHEN attributes IS NULL OR attributes = '' THEN '{}'::jsonb
                        ELSE attributes::jsonb
                    END
                )
                """
            )
            cur.execute(
                "ALTER TABLE edges ALTER COLUMN attributes SET DEFAULT '{}'::jsonb"
            )
        else:
            cur.execute(
                "ALTER TABLE edges ALTER COLUMN attributes SET DEFAULT '{}'::jsonb"
            )

        cur.execute(
            "UPDATE edges SET attributes='{}'::jsonb WHERE attributes IS NULL"
        )

        # Backfill permission metadata for historical permission edges.
        cur.execute(
            """
            UPDATE edges
            SET attributes = jsonb_set(COALESCE(attributes, '{}'::jsonb), '{permission_level}', '"editor"'::jsonb, true)
            WHERE label = 'OWNED_BY'
              AND (attributes->>'permission_level') IS NULL
            """
        )
        cur.execute(
            """
            UPDATE edges
            SET attributes = jsonb_set(COALESCE(attributes, '{}'::jsonb), '{permission_level}', '"viewer"'::jsonb, true)
            WHERE label = 'SHARED_WITH'
              AND (attributes->>'permission_level') IS NULL
            """
        )

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
    def add_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        label: str,
        attrs: Dict[str, Any] | None = None,
        schema_version: str | None = None,
    ) -> None:
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
            edge_def = DEFAULT_SCHEMA.edge_labels.get(label)
            permission_level = edge_def.permission_level if edge_def else None
            attr_dict: Dict[str, Any] = dict(attrs or {})
            if permission_level is not None and "permission_level" not in attr_dict:
                attr_dict["permission_level"] = permission_level
            if schema_version is not None and "schema_version" not in attr_dict:
                attr_dict["schema_version"] = schema_version
            cur.execute(
                "INSERT INTO edges(source, target, label, attributes, created_at) VALUES(%s, %s, %s, %s, %s)",
                (
                    source_node_id,
                    target_node_id,
                    label,
                    json.dumps(attr_dict),
                    int(time.time()),
                ),
            )

    def get_all_edges(self) -> List[Tuple[str, str, str, Dict[str, Any]]]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.source, e.target, e.label, e.attributes
                FROM edges e
                JOIN nodes s ON e.source = s.id
                JOIN nodes t ON e.target = t.id
                WHERE e.redacted=false AND s.redacted=false AND t.redacted=false
                """
            )
            edges: List[Tuple[str, str, str, Dict[str, Any]]] = []
            for source, target, label, raw_attrs in cur.fetchall():
                if raw_attrs in (None, ""):
                    attr_dict: Dict[str, Any] = {}
                elif isinstance(raw_attrs, (dict, list)):
                    attr_dict = dict(cast(Dict[str, Any], raw_attrs))
                elif isinstance(raw_attrs, memoryview):
                    attr_dict = cast(
                        Dict[str, Any], json.loads(raw_attrs.tobytes())
                    )
                else:
                    attr_dict = cast(Dict[str, Any], json.loads(raw_attrs))
                if not isinstance(attr_dict, dict):
                    attr_dict = {}
                edges.append((source, target, label, attr_dict))
            return edges

    def delete_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        label: str,
        attrs: Dict[str, Any] | None = None,
    ) -> None:
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


