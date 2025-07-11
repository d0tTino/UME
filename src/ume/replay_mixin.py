from __future__ import annotations

from typing import TYPE_CHECKING, cast

from .graph_adapter import IGraphAdapter

if TYPE_CHECKING:  # pragma: no cover - for type hints only
    from .event_ledger import EventLedger


class ReplayMixin:
    """Provide ledger replay capabilities for graph adapters."""

    def replay_from_ledger(
        self,
        ledger: "EventLedger",
        start_offset: int = 0,
        end_offset: int | None = None,
        *,
        end_timestamp: int | None = None,
    ) -> int:
        """Replay ledger events into ``self`` starting from ``start_offset``."""
        last = start_offset
        from .event import parse_event
        from .processing import apply_event_to_graph

        adapter = cast(IGraphAdapter, self)

        for off, data in ledger.range(start=start_offset, end=end_offset):
            if end_timestamp is not None and data.get("timestamp", 0) > end_timestamp:
                break
            event = parse_event(data)
            apply_event_to_graph(event, adapter)
            last = off
        return last
