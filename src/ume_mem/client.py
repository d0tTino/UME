from __future__ import annotations

import time
from typing import Optional

from .event import Event, EventType
from .graph import MockGraph
from .graph_adapter import IGraphAdapter
from .processing import apply_event_to_graph, ProcessingError


class UMEClient:
    """Convenience client for interacting with a graph using UME events."""

    def __init__(self, broker: Optional[str] = None, topic: Optional[str] = None, graph: Optional[IGraphAdapter] = None) -> None:
        self.broker = broker
        self.topic = topic
        self.graph: IGraphAdapter = graph or MockGraph()

    def _timestamp(self) -> int:
        return int(time.time())

    def create_node(self, node_id: str, attributes: Optional[dict[str, object]] = None) -> None:
        event = Event(
            event_type=EventType.CREATE_NODE,
            timestamp=self._timestamp(),
            payload={"node_id": node_id, "attributes": attributes or {}},
        )
        apply_event_to_graph(event, self.graph)

    def update_node(self, node_id: str, attributes: dict[str, object]) -> None:
        event = Event(
            event_type=EventType.UPDATE_NODE_ATTRIBUTES,
            timestamp=self._timestamp(),
            payload={"node_id": node_id, "attributes": attributes},
        )
        apply_event_to_graph(event, self.graph)

    def create_edge(self, source_id: str, target_id: str, label: str) -> None:
        event = Event(
            event_type=EventType.CREATE_EDGE,
            timestamp=self._timestamp(),
            node_id=source_id,
            target_node_id=target_id,
            label=label,
            payload={},
        )
        apply_event_to_graph(event, self.graph)

    def delete_edge(self, source_id: str, target_id: str, label: str) -> None:
        event = Event(
            event_type=EventType.DELETE_EDGE,
            timestamp=self._timestamp(),
            node_id=source_id,
            target_node_id=target_id,
            label=label,
            payload={},
        )
        apply_event_to_graph(event, self.graph)

    def get_node(self, node_id: str) -> Optional[dict[str, object]]:
        return self.graph.get_node(node_id)

    def query_neighbors(self, node_id: str, label: Optional[str] = None) -> list[str]:
        return self.graph.find_connected_nodes(node_id, label)

    def clear(self) -> None:
        self.graph.clear()
