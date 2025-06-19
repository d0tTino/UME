from __future__ import annotations

from threading import Lock
from typing import Any, Dict, List, Protocol


class GraphListener(Protocol):
    """Protocol for receiving notifications when the graph changes."""

    def on_node_created(self, node_id: str, attributes: Dict[str, Any]) -> None:
        """Called after a node is created."""

    def on_node_updated(self, node_id: str, attributes: Dict[str, Any]) -> None:
        """Called after a node's attributes are updated."""

    def on_edge_created(
        self, source_node_id: str, target_node_id: str, label: str
    ) -> None:
        """Called after an edge is created."""

    def on_edge_deleted(
        self, source_node_id: str, target_node_id: str, label: str
    ) -> None:
        """Called after an edge is deleted."""


_registered_listeners: List[GraphListener] = []
_listener_lock = Lock()


def register_listener(listener: GraphListener) -> None:
    """Register a GraphListener to receive callbacks."""
    with _listener_lock:
        _registered_listeners.append(listener)


def unregister_listener(listener: GraphListener) -> None:
    """Unregister a previously registered GraphListener."""
    with _listener_lock:
        if listener in _registered_listeners:
            _registered_listeners.remove(listener)


def get_registered_listeners() -> List[GraphListener]:
    """Return a copy of currently registered listeners."""
    with _listener_lock:
        return list(_registered_listeners)
