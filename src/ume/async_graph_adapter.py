"""Asynchronous graph adapter interface and implementation."""

from __future__ import annotations

import asyncio

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, cast

from .persistent_graph import PersistentGraph
from .processing import ProcessingError, DEFAULT_VERSION
from .event import Event, EventType, parse_event
from ._internal.listeners import get_registered_listeners
from .plugins.alignment import get_plugins
from .schema_manager import DEFAULT_SCHEMA_MANAGER
from .graph_adapter import IGraphAdapter, AsyncAdapterMixin


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
        self,
        source_node_id: str,
        target_node_id: str,
        label: str,
        attrs: Dict[str, Any] | None = None,
        schema_version: str | None = None,
    ) -> None:
        pass

    @abstractmethod
    async def get_all_edges(self) -> List[Tuple[str, str, str, Dict[str, Any]]]:
        pass

    @abstractmethod
    async def delete_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        label: str,
        attrs: Dict[str, Any] | None = None,
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


class AsyncGraphAdapterWrapper(AsyncAdapterMixin, IAsyncGraphAdapter):
    """Wrap a synchronous :class:`IGraphAdapter` with async methods."""

    def __init__(self, adapter: "IGraphAdapter") -> None:
        super().__init__(adapter)



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


class AsyncPersistentGraph(AsyncAdapterMixin, AsyncGraphAlgorithmsMixin, IAsyncGraphAdapter):
    """Asynchronous wrapper around :class:`PersistentGraph`."""

    def __init__(self, adapter: "PersistentGraph") -> None:
        super().__init__(adapter)
        self._adapter: PersistentGraph = adapter

    @classmethod
    async def create(cls, db_path: str | None = None) -> "AsyncPersistentGraph":
        adapter = await asyncio.to_thread(PersistentGraph, db_path)
        return cls(adapter)

    async def add_score(
        self, task_id: str | None, agent_id: str | None, score: float
    ) -> None:
        await asyncio.to_thread(self._adapter.add_score, task_id, agent_id, score)

    async def get_scores(self) -> List[Tuple[str | None, str | None, float]]:
        return await asyncio.to_thread(self._adapter.get_scores)

    async def node_count(self) -> int:
        return await asyncio.to_thread(lambda: self._adapter.node_count)


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


async def ingest_event_async(
    data: Dict[str, Any],
    graph: IAsyncGraphAdapter,
    *,
    schema_version: str | None = None,
) -> None:
    """Validate ``data`` and apply the resulting event to ``graph`` asynchronously."""
    if "event" in data and isinstance(data["event"], dict):
        event_dict = cast(Dict[str, Any], data["event"])
        detected_version = cast(str | None, data.get("schema_version"))
    else:
        event_dict = data
        detected_version = cast(str | None, data.get("schema_version"))
    event = parse_event(event_dict)
    effective_version = schema_version or detected_version or DEFAULT_VERSION
    await apply_event_to_async_graph(event, graph, schema_version=effective_version)


__all__ = [
    "IAsyncGraphAdapter",
    "AsyncGraphAdapterWrapper",
    "AsyncPersistentGraph",
    "apply_event_to_async_graph",
    "ingest_event_async",
]

