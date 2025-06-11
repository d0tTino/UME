from __future__ import annotations

from typing import Protocol, Dict, Any, List


class GraphListener(Protocol):
    """Protocol for receiving notifications when the graph changes."""

    def on_node_created(self, node_id: str, attributes: Dict[str, Any]) -> None:
        """Called after a node is created."""

    def on_node_updated(self, node_id: str, attributes: Dict[str, Any]) -> None:
        """Called after a node's attributes are updated."""

    def on_edge_created(self, source_node_id: str, target_node_id: str, label: str) -> None:
        """Called after an edge is created."""

    def on_edge_deleted(self, source_node_id: str, target_node_id: str, label: str) -> None:
        """Called after an edge is deleted."""


_registered_listeners: List[GraphListener] = []


def register_listener(listener: GraphListener) -> None:
    """Register a GraphListener to receive callbacks."""
    _registered_listeners.append(listener)


def unregister_listener(listener: GraphListener) -> None:
    """Unregister a previously registered GraphListener."""
    if listener in _registered_listeners:
        _registered_listeners.remove(listener)


def get_registered_listeners() -> List[GraphListener]:
    """Return a copy of currently registered listeners."""
    return list(_registered_listeners)
