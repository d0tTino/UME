import sqlite3
import json
from typing import Dict, Any, Optional, List, Tuple
from .graph_adapter import IGraphAdapter
from .processing import ProcessingError
from .audit import log_audit_entry
from .config import settings


class PersistentGraph(IGraphAdapter):
    """SQLite-backed persistent graph implementation."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.UME_DB_PATH
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
        user_id = settings.UME_AGENT_ID
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
        user_id = settings.UME_AGENT_ID
        log_audit_entry(
            user_id,
            f"redact_edge {source_node_id} {target_node_id} {label}",
        )

    # ---- Traversal and pathfinding ---------------------------------

    def shortest_path(self, source_id: str, target_id: str) -> List[str]:
        if not self.node_exists(source_id) or not self.node_exists(target_id):
            return []
        visited = {source_id: None}
        queue: List[str] = [source_id]
        while queue:
            current = queue.pop(0)
            if current == target_id:
                break
            for neighbor in self.find_connected_nodes(current):
                if neighbor not in visited:
                    visited[neighbor] = current
                    queue.append(neighbor)
        if target_id not in visited:
            return []
        path = [target_id]
        while visited[path[-1]] is not None:
            prev = visited[path[-1]]
            assert prev is not None
            path.append(prev)
        path.reverse()
        return path

    def traverse(
        self,
        start_node_id: str,
        depth: int,
        edge_label: Optional[str] = None,
    ) -> List[str]:
        if not self.node_exists(start_node_id):
            raise ProcessingError(f"Node '{start_node_id}' not found.")
        visited: set[str] = {start_node_id}
        queue: List[tuple[str, int]] = [(start_node_id, 0)]
        result: List[str] = []
        while queue:
            node, d = queue.pop(0)
            if d >= depth:
                continue
            for neighbor in self.find_connected_nodes(node, edge_label):
                if neighbor not in visited:
                    visited.add(neighbor)
                    result.append(neighbor)
                    queue.append((neighbor, d + 1))
        return result

    def extract_subgraph(
        self,
        start_node_id: str,
        depth: int,
        edge_label: Optional[str] = None,
        since_timestamp: Optional[int] = None,
    ) -> Dict[str, Any]:
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Tuple[str, str, str]] = []
        all_edges = self.get_all_edges()
        adj: Dict[str, List[Tuple[str, str]]] = {}
        for src, tgt, lbl in all_edges:
            adj.setdefault(src, []).append((tgt, lbl))

        to_visit = [(start_node_id, 0)]
        visited: set[str] = set()
        while to_visit:
            node, d = to_visit.pop(0)
            if node in visited or d > depth:
                continue
            visited.add(node)
            data = self.get_node(node) or {}
            include = True
            if since_timestamp is not None:
                ts = data.get("timestamp")
                if ts is None or int(ts) < since_timestamp:
                    include = False
            if include:
                nodes[node] = data.copy()
            if d == depth:
                continue
            for tgt, lbl in adj.get(node, []):
                if edge_label is None or lbl == edge_label:
                    edges.append((node, tgt, lbl))
                    to_visit.append((tgt, d + 1))
        return {"nodes": nodes, "edges": edges}

    def constrained_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int | None = None,
        edge_label: str | None = None,
        since_timestamp: int | None = None,
    ) -> List[str]:
        if not self.node_exists(source_id) or not self.node_exists(target_id):
            return []
        visited: dict[str, str | None] = {source_id: None}
        queue: List[tuple[str, int]] = [(source_id, 0)]
        while queue:
            node, depth = queue.pop(0)
            if node == target_id:
                break
            if max_depth is not None and depth >= max_depth:
                continue
            for neighbor in self.find_connected_nodes(node, edge_label):
                if neighbor in visited:
                    continue
                if since_timestamp is not None:
                    data = self.get_node(neighbor) or {}
                    ts = data.get("timestamp")
                    if ts is None or int(ts) < since_timestamp:
                        continue
                visited[neighbor] = node
                queue.append((neighbor, depth + 1))
        if target_id not in visited:
            return []
        path = [target_id]
        while visited[path[-1]] is not None:
            prev = visited[path[-1]]
            assert prev is not None
            path.append(prev)
        path.reverse()
        return path
