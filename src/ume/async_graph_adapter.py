"""Asynchronous graph adapter interface and implementation."""

from __future__ import annotations

import asyncio
import warnings

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, cast

from .persistent_graph import PersistentGraph
from .processing import DEFAULT_VERSION, apply_event_to_graph
from .event import Event, EventError
from .kernel.graph_adapter import IGraphAdapter, AsyncAdapterMixin
from .services.mutate import MutationError, raise_for_rejected_outcome
from .services.event_processor import EventProcessorService


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


class _AsyncToSyncGraphAdapter(IGraphAdapter):
    def __init__(self, graph: IAsyncGraphAdapter) -> None:
        self._graph = graph

    def _await(self, coro: Any) -> Any:
        return asyncio.run(coro)

    def add_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        self._await(self._graph.add_node(node_id, attributes))

    def update_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        self._await(self._graph.update_node(node_id, attributes))

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self._await(self._graph.get_node(node_id))

    def node_exists(self, node_id: str) -> bool:
        return cast(bool, self._await(self._graph.node_exists(node_id)))

    def dump(self) -> Dict[str, Any]:
        return cast(Dict[str, Any], self._await(self._graph.dump()))

    def clear(self) -> None:
        self._await(self._graph.clear())

    def get_all_node_ids(self) -> list[str]:
        return cast(list[str], self._await(self._graph.get_all_node_ids()))

    def find_connected_nodes(
        self, node_id: str, edge_label: Optional[str] = None
    ) -> list[str]:
        return cast(list[str], self._await(self._graph.find_connected_nodes(node_id, edge_label)))

    def add_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        label: str,
        attrs: Dict[str, Any] | None = None,
        schema_version: str | None = None,
    ) -> None:
        self._await(
            self._graph.add_edge(
                source_node_id,
                target_node_id,
                label,
                attrs,
                schema_version,
            )
        )

    def get_all_edges(self) -> list[tuple[str, str, str, Dict[str, Any]]]:
        return cast(list[tuple[str, str, str, Dict[str, Any]]], self._await(self._graph.get_all_edges()))

    def delete_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        label: str,
        attrs: Dict[str, Any] | None = None,
    ) -> None:
        self._await(self._graph.delete_edge(source_node_id, target_node_id, label, attrs))

    def redact_node(self, node_id: str) -> None:
        self._await(self._graph.redact_node(node_id))

    def redact_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        self._await(self._graph.redact_edge(source_node_id, target_node_id, label))

    def close(self) -> None:
        self._await(self._graph.close())

    def shortest_path(self, source_id: str, target_id: str) -> list[str]:
        return cast(list[str], self._await(cast(Any, self._graph).shortest_path(source_id, target_id)))

    def traverse(
        self,
        start_node_id: str,
        depth: int,
        edge_label: Optional[str] = None,
    ) -> list[str]:
        return cast(list[str], self._await(cast(Any, self._graph).traverse(start_node_id, depth, edge_label)))

    def extract_subgraph(
        self,
        start_node_id: str,
        depth: int,
        edge_label: Optional[str] = None,
        since_timestamp: Optional[int] = None,
    ) -> Dict[str, Any]:
        return cast(
            Dict[str, Any],
            self._await(
                cast(Any, self._graph).extract_subgraph(
                    start_node_id,
                    depth,
                    edge_label,
                    since_timestamp,
                )
            ),
        )

    def constrained_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: Optional[int] = None,
        edge_label: Optional[str] = None,
        since_timestamp: Optional[int] = None,
    ) -> list[str]:
        return cast(
            list[str],
            self._await(
                cast(Any, self._graph).constrained_path(
                    source_id,
                    target_id,
                    max_depth,
                    edge_label,
                    since_timestamp,
                )
            ),
        )


_async_event_processor = EventProcessorService()


async def _apply_event_via_registry(
    event: Event,
    graph: IAsyncGraphAdapter,
    *,
    schema_version: str,
) -> None:
    shim = _AsyncToSyncGraphAdapter(graph)
    await asyncio.to_thread(apply_event_to_graph, event, shim, schema_version=schema_version)


async def apply_event_to_async_graph(
    event: Event,
    graph: IAsyncGraphAdapter,
    *,
    schema_version: str = DEFAULT_VERSION,
) -> None:
    """Deprecated helper retained for backward compatibility."""
    warnings.warn(
        "apply_event_to_async_graph() is deprecated as a standalone decision engine; "
        "use ingest_event_async() and shared pipeline orchestration instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    await _apply_event_via_registry(event, graph, schema_version=schema_version)


async def ingest_event_async(
    data: Dict[str, Any],
    graph: IAsyncGraphAdapter,
    *,
    schema_version: str | None = None,
    event: Event | None = None,
) -> None:
    """Apply a canonical envelope/event pair to ``graph`` asynchronously."""
    canonical = data
    if event is not None:
        warnings.warn(
            "ingest_event_async(event=...) is deprecated; pass transport payload only.",
            DeprecationWarning,
            stacklevel=2,
        )

    async def _project(context: Any) -> dict[str, Any]:
        effective_event = context.effective_event
        if effective_event is None:
            raise EventError("effective_event_missing")
        metadata = context.canonical_event.get("metadata", {}) if context.canonical_event else {}
        detected_version = metadata.get("schema_version") if isinstance(metadata, dict) else None
        effective_version = schema_version or detected_version or DEFAULT_VERSION
        await _apply_event_via_registry(effective_event, graph, schema_version=effective_version)
        return {"schema_version": effective_version}

    result = await _async_event_processor.process_payload_async(
        canonical,
        source="async_ingest",
        projector=_project,
    )
    try:
        raise_for_rejected_outcome(result)
    except MutationError as exc:
        raise EventError(str(exc)) from exc


__all__ = [
    "IAsyncGraphAdapter",
    "AsyncGraphAdapterWrapper",
    "AsyncPersistentGraph",
    "apply_event_to_async_graph",
    "ingest_event_async",
]
