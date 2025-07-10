"""Event ingestion helpers used by API and gRPC layers."""

from __future__ import annotations

from typing import Iterable, Dict, Any

from ..event import Event, parse_event
from ..processing import apply_event_to_graph
from ..graph_adapter import IGraphAdapter

__all__ = [
    "validate_event",
    "apply_event",
    "ingest_event",
    "ingest_events_batch",
]


def validate_event(data: Dict[str, Any]) -> Event:
    """Parse ``data`` into an :class:`~ume.event.Event`."""
    return parse_event(data)


def apply_event(event: Event, graph: IGraphAdapter) -> None:
    """Apply ``event`` to ``graph`` using :func:`~ume.processing.apply_event_to_graph`."""
    apply_event_to_graph(event, graph)


def ingest_event(data: Dict[str, Any], graph: IGraphAdapter) -> None:
    """Validate ``data`` and apply the resulting event to ``graph``."""
    event = validate_event(data)
    apply_event(event, graph)


def ingest_events_batch(events: Iterable[Dict[str, Any]], graph: IGraphAdapter) -> None:
    """Sequentially ingest multiple events into ``graph``."""
    for data in events:
        ingest_event(data, graph)
