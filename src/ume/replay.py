from __future__ import annotations

from typing import TYPE_CHECKING

from .graph_adapter import IGraphAdapter

if TYPE_CHECKING:  # pragma: no cover - for type hints only
    from .event_ledger import EventLedger


def replay_from_ledger(
    graph: IGraphAdapter,
    ledger: "EventLedger",
    start_offset: int = 0,
    end_offset: int | None = None,
    *,
    end_timestamp: int | None = None,
) -> int:
    """Replay ledger events into ``graph`` starting from ``start_offset``."""
    last = start_offset
    from .event import parse_event
    from .processing import apply_event_to_graph

    for off, data in ledger.range(start=start_offset, end=end_offset):
        if end_timestamp is not None and data.get("timestamp", 0) > end_timestamp:
            break
        event = parse_event(data)
        apply_event_to_graph(event, graph)
        last = off
    return last


def build_graph_from_ledger(
    ledger: "EventLedger",
    graph: IGraphAdapter | None = None,
    *,
    end_offset: int | None = None,
    end_timestamp: int | None = None,
    db_path: str | None = ":memory:",
) -> IGraphAdapter:
    """Return ``graph`` populated from ``ledger``."""
    if graph is None:
        from .persistent_graph import PersistentGraph

        graph = PersistentGraph(db_path, check_same_thread=False)
    replay_from_ledger(
        graph,
        ledger,
        start_offset=0,
        end_offset=end_offset,
        end_timestamp=end_timestamp,
    )
    return graph
