# src/ume/__init__.py
"""
Universal Memory Engine (UME) core package.
"""
from .event import Event, parse_event, EventError
from .graph import MockGraph
from .graph_adapter import IGraphAdapter
from .processing import apply_event_to_graph, ProcessingError
from .snapshot import snapshot_graph_to_file, load_graph_from_file, SnapshotError
from .config import CLI_SNAPSHOT_PATH, API_SNAPSHOT_PATH, CLI_SNAPSHOT_DIR # Add this

__all__ = [
    # event.py
    "Event", "parse_event", "EventError",
    # graph_adapter.py
    "IGraphAdapter",
    # graph.py
    "MockGraph",
    # processing.py
    "apply_event_to_graph", "ProcessingError",
    # snapshot.py
    "snapshot_graph_to_file", "load_graph_from_file", "SnapshotError",
    # config.py
    "CLI_SNAPSHOT_PATH", "API_SNAPSHOT_PATH", "CLI_SNAPSHOT_DIR",
]
