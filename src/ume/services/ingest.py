"""Event ingestion helpers used by API and gRPC layers."""

from __future__ import annotations

from typing import Iterable, Dict, Any

from ..event import parse_event
from ..processing import apply_event_to_graph
from ..graph_adapter import IGraphAdapter

__all__ = ["ingest_event", "ingest_events_batch"]


def ingest_event(data: Dict[str, Any], graph: IGraphAdapter) -> None:
    """Parse and apply a single event to ``graph``."""
    event = parse_event(data)
    apply_event_to_graph(event, graph)


def ingest_events_batch(events: Iterable[Dict[str, Any]], graph: IGraphAdapter) -> None:
    """Sequentially ingest multiple events into ``graph``."""
    for data in events:
        ingest_event(data, graph)
