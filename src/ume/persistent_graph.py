import sqlite3
import json
import os
from typing import Dict, Any, Optional, List, Tuple
from .graph_adapter import IGraphAdapter
from .processing import ProcessingError
from .audit import log_audit_entry


class PersistentGraph(IGraphAdapter):
    """SQLite-backed persistent graph implementation."""

    def __init__(self, db_path: str = "ume_graph.db") -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        with self.conn:
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS nodes (id TEXT PRIMARY KEY, attributes TEXT, redacted INTEGER DEFAULT 0)"
            )
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS edges (source TEXT, target TEXT, label TEXT, redacted INTEGER DEFAULT 0, PRIMARY KEY (source, target, label))"
            )

    def close(self) -> None:
        self.conn.close()

    def add_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO nodes(id, attributes) VALUES(?, ?)",
                    (node_id, json.dumps(attributes)),
                )
        except sqlite3.IntegrityError:
            raise ProcessingError(f"Node '{node_id}' already exists.")

    def update_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        cur = self.conn.execute("SELECT attributes FROM nodes WHERE id=?", (node_id,))
        row = cur.fetchone()
        if row is None:
            raise ProcessingError(f"Node '{node_id}' not found for update.")
        data = json.loads(row["attributes"])
        data.update(attributes)
        with self.conn:
            self.conn.execute(
                "UPDATE nodes SET attributes=? WHERE id=?",
                (json.dumps(data), node_id),
            )

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.execute(
            "SELECT attributes FROM nodes WHERE id=? AND redacted=0",
            (node_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return json.loads(row["attributes"])

    def node_exists(self, node_id: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM nodes WHERE id=? AND redacted=0",
            (node_id,),
        )
        return cur.fetchone() is not None

    def get_all_node_ids(self) -> List[str]:
        cur = self.conn.execute("SELECT id FROM nodes WHERE redacted=0")
        return [row["id"] for row in cur.fetchall()]

    def add_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        if not self.node_exists(source_node_id) or not self.node_exists(target_node_id):
            raise ProcessingError(
                f"Both source node '{source_node_id}' and target node '{target_node_id}' must exist to add an edge."
            )
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO edges(source, target, label) VALUES(?, ?, ?)",
                    (source_node_id, target_node_id, label),
                )
        except sqlite3.IntegrityError:
            raise ProcessingError(
                f"Edge ({source_node_id}, {target_node_id}, {label}) already exists."
            )

    def get_all_edges(self) -> List[Tuple[str, str, str]]:
        cur = self.conn.execute(
            """
            SELECT e.source, e.target, e.label
            FROM edges e
            JOIN nodes s ON e.source = s.id
            JOIN nodes t ON e.target = t.id
            WHERE e.redacted=0 AND s.redacted=0 AND t.redacted=0
            """
        )
        return [(row["source"], row["target"], row["label"]) for row in cur.fetchall()]

    def delete_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        with self.conn:
            cur = self.conn.execute(
                "DELETE FROM edges WHERE source=? AND target=? AND label=?",
                (source_node_id, target_node_id, label),
            )
            if cur.rowcount == 0:
                edge_tuple = (source_node_id, target_node_id, label)
                raise ProcessingError(
                    f"Edge {edge_tuple} does not exist and cannot be deleted."
                )

    def find_connected_nodes(
        self, node_id: str, edge_label: Optional[str] = None
    ) -> List[str]:
        if not self.node_exists(node_id):
            raise ProcessingError(f"Node '{node_id}' not found.")
        if edge_label:
            cur = self.conn.execute(
                """
                SELECT e.target FROM edges e
                JOIN nodes s ON e.source = s.id
                JOIN nodes t ON e.target = t.id
                WHERE e.source=? AND e.label=?
                  AND e.redacted=0 AND s.redacted=0 AND t.redacted=0
                """,
                (node_id, edge_label),
            )
        else:
            cur = self.conn.execute(
                """
                SELECT e.target FROM edges e
                JOIN nodes s ON e.source = s.id
                JOIN nodes t ON e.target = t.id
                WHERE e.source=? AND e.redacted=0 AND s.redacted=0 AND t.redacted=0
                """,
                (node_id,),
            )
        return [row["target"] for row in cur.fetchall()]

    def clear(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM edges")
            self.conn.execute("DELETE FROM nodes")

    @property
    def node_count(self) -> int:
        cur = self.conn.execute("SELECT COUNT(*) AS cnt FROM nodes WHERE redacted=0")
        row = cur.fetchone()
        return int(row["cnt"]) if row else 0

    def dump(self) -> Dict[str, Any]:
        nodes: Dict[str, Any] = {}
        for row in self.conn.execute(
            "SELECT id, attributes FROM nodes WHERE redacted=0"
        ):
            nodes[row["id"]] = json.loads(row["attributes"])
        edges = self.get_all_edges()
        return {"nodes": nodes, "edges": edges}

    def redact_node(self, node_id: str) -> None:
        with self.conn:
            cur = self.conn.execute(
                "UPDATE nodes SET redacted=1 WHERE id=?",
                (node_id,),
            )
            if cur.rowcount == 0:
                raise ProcessingError(f"Node '{node_id}' not found to redact.")
        user_id = os.environ.get("UME_AGENT_ID", "SYSTEM")
        log_audit_entry(user_id, f"redact_node {node_id}")

    def redact_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        with self.conn:
            cur = self.conn.execute(
                "UPDATE edges SET redacted=1 WHERE source=? AND target=? AND label=?",
                (source_node_id, target_node_id, label),
            )
            if cur.rowcount == 0:
                edge_tuple = (source_node_id, target_node_id, label)
                raise ProcessingError(
                    f"Edge {edge_tuple} does not exist and cannot be redacted."
                )
        user_id = os.environ.get("UME_AGENT_ID", "SYSTEM")
        log_audit_entry(
            user_id,
            f"redact_edge {source_node_id} {target_node_id} {label}",
        )
