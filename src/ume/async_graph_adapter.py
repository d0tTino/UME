"""Asynchronous graph adapter interface and implementation."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, cast

import aiosqlite

from .config import settings
from .processing import ProcessingError, DEFAULT_VERSION
from .event import Event, EventType, parse_event
from ._internal.listeners import get_registered_listeners
from .plugins.alignment import get_plugins
from .schema_manager import DEFAULT_SCHEMA_MANAGER


class IAsyncGraphAdapter(ABC):
    """Async version of :class:`~ume.graph_adapter.IGraphAdapter`."""

    @abstractmethod
    async def add_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    async def update_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    async def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    async def node_exists(self, node_id: str) -> bool:
        pass

    @abstractmethod
    async def dump(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def clear(self) -> None:
        pass

    @abstractmethod
    async def get_all_node_ids(self) -> List[str]:
        pass

    @abstractmethod
    async def find_connected_nodes(
        self, node_id: str, edge_label: Optional[str] = None
    ) -> List[str]:
        pass

    @abstractmethod
    async def add_edge(
        self, source_node_id: str, target_node_id: str, label: str
    ) -> None:
        pass

    @abstractmethod
    async def get_all_edges(self) -> List[Tuple[str, str, str]]:
        pass

    @abstractmethod
    async def delete_edge(
        self, source_node_id: str, target_node_id: str, label: str
    ) -> None:
        pass

    @abstractmethod
    async def redact_node(self, node_id: str) -> None:
        pass

    @abstractmethod
    async def redact_edge(
        self, source_node_id: str, target_node_id: str, label: str
    ) -> None:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass


class AsyncGraphAlgorithmsMixin:
    """Asynchronous versions of traversal helpers."""

    async def shortest_path(self, source_id: str, target_id: str) -> List[str]:
        graph = cast(IAsyncGraphAdapter, self)
        if not await graph.node_exists(source_id) or not await graph.node_exists(target_id):
            return []
        visited: Dict[str, Optional[str]] = {source_id: None}
        queue: List[str] = [source_id]
        while queue:
            current = queue.pop(0)
            if current == target_id:
                break
            for neighbor in await graph.find_connected_nodes(current):
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


class AsyncPersistentGraph(AsyncGraphAlgorithmsMixin, IAsyncGraphAdapter):
    """SQLite-backed graph adapter using ``aiosqlite``."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.conn = conn

    @classmethod
    async def create(cls, db_path: str | None = None) -> "AsyncPersistentGraph":
        conn = await aiosqlite.connect(db_path or settings.UME_DB_PATH)
        conn.row_factory = aiosqlite.Row
        self = cls(conn)
        await self._create_tables()
        return self

    async def _create_tables(self) -> None:
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                attributes TEXT,
                redacted INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT (strftime('%s','now'))
            )
            """
        )
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS edges (
                source TEXT,
                target TEXT,
                label TEXT,
                redacted INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT (strftime('%s','now')),
                PRIMARY KEY (source, target, label)
            )
            """
        )
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                agent_id TEXT,
                score REAL
            )
            """
        )
        await self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_edges_source ON edges (source)"
        )
        await self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_edges_target ON edges (target)"
        )
        await self.conn.commit()

    async def close(self) -> None:
        await self.conn.close()

    async def add_node(
        self, node_id: str, attributes: Dict[str, Any], *, created_at: int | None = None
    ) -> None:
        try:
            await self.conn.execute(
                "INSERT INTO nodes(id, attributes, created_at) VALUES(?, ?, ?)",
                (node_id, json.dumps(attributes), created_at or int(time.time())),
            )
            await self.conn.commit()
        except aiosqlite.IntegrityError:
            raise ProcessingError(f"Node '{node_id}' already exists.")

    async def update_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        cur = await self.conn.execute(
            "SELECT attributes FROM nodes WHERE id=? AND redacted=0", (node_id,)
        )
        row = await cur.fetchone()
        await cur.close()
        if row is None:
            raise ProcessingError(f"Node '{node_id}' not found for update.")
        data = json.loads(row["attributes"])
        data.update(attributes)
        await self.conn.execute(
            "UPDATE nodes SET attributes=? WHERE id=?",
            (json.dumps(data), node_id),
        )
        await self.conn.commit()

    async def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        cur = await self.conn.execute(
            "SELECT attributes FROM nodes WHERE id=? AND redacted=0",
            (node_id,),
        )
        row = await cur.fetchone()
        await cur.close()
        if row is None:
            return None
        return cast(Dict[str, Any], json.loads(row["attributes"]))

    async def node_exists(self, node_id: str) -> bool:
        cur = await self.conn.execute(
            "SELECT 1 FROM nodes WHERE id=? AND redacted=0",
            (node_id,),
        )
        row = await cur.fetchone()
        await cur.close()
        return row is not None

    async def get_all_node_ids(self) -> List[str]:
        cur = await self.conn.execute("SELECT id FROM nodes WHERE redacted=0")
        rows = await cur.fetchall()
        await cur.close()
        return [row["id"] for row in rows]

    async def add_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        label: str,
        *,
        created_at: int | None = None,
    ) -> None:
        if not await self.node_exists(source_node_id) or not await self.node_exists(
            target_node_id
        ):
            raise ProcessingError(
                f"Both source node '{source_node_id}' and target node '{target_node_id}' must exist to add an edge."
            )
        try:
            await self.conn.execute(
                "INSERT INTO edges(source, target, label, created_at) VALUES(?, ?, ?, ?)",
                (
                    source_node_id,
                    target_node_id,
                    label,
                    created_at or int(time.time()),
                ),
            )
            await self.conn.commit()
        except aiosqlite.IntegrityError:
            raise ProcessingError(
                f"Edge ({source_node_id}, {target_node_id}, {label}) already exists."
            )

    async def get_all_edges(self) -> List[Tuple[str, str, str]]:
        cur = await self.conn.execute(
            """
            SELECT e.source, e.target, e.label
            FROM edges e
            JOIN nodes s ON e.source = s.id
            JOIN nodes t ON e.target = t.id
            WHERE e.redacted=0 AND s.redacted=0 AND t.redacted=0
            """
        )
        rows = await cur.fetchall()
        await cur.close()
        return [(row["source"], row["target"], row["label"]) for row in rows]

    async def delete_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        cur = await self.conn.execute(
            "DELETE FROM edges WHERE source=? AND target=? AND label=?",
            (source_node_id, target_node_id, label),
        )
        await self.conn.commit()
        if cur.rowcount == 0:
            raise ProcessingError(
                f"Edge {(source_node_id, target_node_id, label)} does not exist and cannot be deleted."
            )

    async def find_connected_nodes(
        self, node_id: str, edge_label: Optional[str] = None
    ) -> List[str]:
        if not await self.node_exists(node_id):
            raise ProcessingError(f"Node '{node_id}' not found.")
        if edge_label:
            cur = await self.conn.execute(
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
            cur = await self.conn.execute(
                """
                SELECT e.target FROM edges e
                JOIN nodes s ON e.source = s.id
                JOIN nodes t ON e.target = t.id
                WHERE e.source=? AND e.redacted=0 AND s.redacted=0 AND t.redacted=0
                """,
                (node_id,),
            )
        rows = await cur.fetchall()
        await cur.close()
        return [row["target"] for row in rows]

    async def add_score(self, task_id: str | None, agent_id: str | None, score: float) -> None:
        await self.conn.execute(
            "INSERT INTO scores(task_id, agent_id, score) VALUES(?, ?, ?)",
            (task_id, agent_id, score),
        )
        await self.conn.commit()

    async def get_scores(self) -> List[Tuple[str | None, str | None, float]]:
        cur = await self.conn.execute(
            "SELECT task_id, agent_id, score FROM scores"
        )
        rows = await cur.fetchall()
        await cur.close()
        return [
            (row["task_id"], row["agent_id"], float(row["score"])) for row in rows
        ]

    async def clear(self) -> None:
        await self.conn.execute("DELETE FROM edges")
        await self.conn.execute("DELETE FROM nodes")
        await self.conn.execute("DELETE FROM scores")
        await self.conn.commit()

    async def node_count(self) -> int:
        cur = await self.conn.execute(
            "SELECT COUNT(*) AS cnt FROM nodes WHERE redacted=0"
        )
        row = await cur.fetchone()
        await cur.close()
        return int(row["cnt"]) if row else 0

    async def dump(self) -> Dict[str, Any]:
        nodes: Dict[str, Any] = {}
        async with self.conn.execute(
            "SELECT id, attributes FROM nodes WHERE redacted=0"
        ) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                nodes[row["id"]] = json.loads(row["attributes"])
        edges = await self.get_all_edges()
        return {"nodes": nodes, "edges": edges}

    async def redact_node(self, node_id: str) -> None:
        cur = await self.conn.execute(
            "UPDATE nodes SET redacted=1 WHERE id=?",
            (node_id,),
        )
        await self.conn.commit()
        if cur.rowcount == 0:
            raise ProcessingError(f"Node '{node_id}' not found to redact.")

    async def redact_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        cur = await self.conn.execute(
            "UPDATE edges SET redacted=1 WHERE source=? AND target=? AND label=?",
            (source_node_id, target_node_id, label),
        )
        await self.conn.commit()
        if cur.rowcount == 0:
            raise ProcessingError(
                f"Edge {(source_node_id, target_node_id, label)} does not exist and cannot be redacted."
            )


async def apply_event_to_async_graph(
    event: Event,
    graph: IAsyncGraphAdapter,
    *,
    schema_version: str = DEFAULT_VERSION,
) -> None:
    """Asynchronous equivalent of :func:`ume.processing.apply_event_to_graph`."""
    for plugin in get_plugins():
        plugin.validate(event)

    if event.event_type == EventType.CREATE_NODE:
        node_id = event.payload.get("node_id")
        if not node_id or not isinstance(node_id, str):
            raise ProcessingError("Invalid node_id for CREATE_NODE")
        attributes = event.payload.get("attributes", {})
        if not isinstance(attributes, dict):
            raise ProcessingError("'attributes' must be a dictionary")
        node_type = attributes.get("type")
        if node_type is not None:
            schema = DEFAULT_SCHEMA_MANAGER.get_schema(schema_version)
            schema.validate_node_type(str(node_type))
        await graph.add_node(node_id, attributes)
        for listener in get_registered_listeners():
            listener.on_node_created(node_id, attributes)
    elif event.event_type == EventType.UPDATE_NODE_ATTRIBUTES:
        node_id = event.payload.get("node_id")
        if not node_id or not isinstance(node_id, str):
            raise ProcessingError("Invalid node_id for UPDATE_NODE_ATTRIBUTES")
        if "attributes" not in event.payload:
            raise ProcessingError("Missing 'attributes' key in payload")
        attributes = event.payload["attributes"]
        if not isinstance(attributes, dict) or not attributes:
            raise ProcessingError("'attributes' must be a non-empty dictionary")
        await graph.update_node(node_id, attributes)
        for listener in get_registered_listeners():
            listener.on_node_updated(node_id, attributes)
    elif event.event_type in {EventType.CREATE_EDGE, EventType.CREATE_ONTOLOGY_RELATION}:
        source_node_id = event.node_id
        target_node_id = event.target_node_id
        label = event.label
        if not (
            isinstance(source_node_id, str)
            and isinstance(target_node_id, str)
            and isinstance(label, str)
        ):
            raise ProcessingError("Invalid edge fields")
        schema = DEFAULT_SCHEMA_MANAGER.get_schema(schema_version)
        schema.validate_edge_label(label)
        await graph.add_edge(source_node_id, target_node_id, label)
        for listener in get_registered_listeners():
            listener.on_edge_created(source_node_id, target_node_id, label)
    elif event.event_type == EventType.DELETE_EDGE:
        source_node_id = event.node_id
        target_node_id = event.target_node_id
        label = event.label
        if not (
            isinstance(source_node_id, str)
            and isinstance(target_node_id, str)
            and isinstance(label, str)
        ):
            raise ProcessingError("Invalid edge fields")
        await graph.delete_edge(source_node_id, target_node_id, label)
        for listener in get_registered_listeners():
            listener.on_edge_deleted(source_node_id, target_node_id, label)
    else:
        raise ProcessingError(f"Unknown event_type '{event.event_type}'")


async def ingest_event_async(data: Dict[str, Any], graph: IAsyncGraphAdapter) -> None:
    """Validate ``data`` and apply the resulting event to ``graph`` asynchronously."""
    event = parse_event(data)
    await apply_event_to_async_graph(event, graph)

