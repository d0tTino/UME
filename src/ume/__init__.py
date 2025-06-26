# src/ume/__init__.py
"""
Universal Memory Engine (UME) core package.
"""

from .event import Event, parse_event, EventError
from .graph import MockGraph
from .graph_adapter import IGraphAdapter
from .adapters import Neo4jAdapter, LanceDBAdapter, get_adapter
from .processing import apply_event_to_graph, ProcessingError
from .policy import RegoPolicyMiddleware
from .snapshot import (
    snapshot_graph_to_file,
    load_graph_from_file,
    SnapshotError,
)  # Modify this import

__all__ = [
    "Event",
    "parse_event",
    "EventError",
    "MockGraph",
    "IGraphAdapter",
    "apply_event_to_graph",
    "ProcessingError",
    "RegoPolicyMiddleware",
    "snapshot_graph_to_file",
    "load_graph_from_file",  # Add this
    "SnapshotError",  # Add this
    "Neo4jAdapter",
    "LanceDBAdapter",
    "get_adapter",
]
