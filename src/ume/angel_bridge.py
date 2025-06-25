"""Angel Bridge service for generating daily summaries from recent events."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Dict, Any, List
import logging
import time
import json

from .persistent_graph import PersistentGraph

from .config import settings

logger = logging.getLogger(__name__)


class AngelBridge:
    """Consume recent events and emit a daily summary."""

    def __init__(self, lookback_hours: int | None = None) -> None:
        self.lookback_hours = lookback_hours or settings.ANGEL_BRIDGE_LOOKBACK_HOURS

    def consume_events(self) -> List[Dict[str, Any]]:
        """Return events from the last ``lookback_hours``.

        This stub implementation returns an empty list. A real implementation
        would query an event store or database for events within the given time
        window.
        """

        logger.debug("Consuming events for last %s hours", self.lookback_hours)
        cutoff = int(time.time()) - self.lookback_hours * 3600
        events: List[Dict[str, Any]] = []
        graph = PersistentGraph()
        try:
            cur = graph.conn.execute(
                "SELECT id, attributes, created_at FROM nodes "
                "WHERE redacted=0 AND created_at >= ?",
                (cutoff,),
            )
            for row in cur.fetchall():
                events.append(
                    {
                        "type": "node",
                        "id": row["id"],
                        "timestamp": row["created_at"],
                        "attributes": json.loads(row["attributes"]),
                    }
                )

            cur = graph.conn.execute(
                "SELECT source, target, label, created_at FROM edges "
                "WHERE redacted=0 AND created_at >= ?",
                (cutoff,),
            )
            for row in cur.fetchall():
                events.append(
                    {
                        "type": "edge",
                        "source": row["source"],
                        "target": row["target"],
                        "label": row["label"],
                        "timestamp": row["created_at"],
                    }
                )
        finally:
            graph.close()

        return events

    def generate_summary(self, events: Iterable[Dict[str, Any]]) -> str:
        """Generate a text summary for the provided events."""
        count = len(list(events))
        today = datetime.utcnow().date()
        return f"Summary for {today}: {count} events"

    def emit_daily_summary(self) -> str:
        """Consume events and return the summary string."""
        events = self.consume_events()
        summary = self.generate_summary(events)
        logger.info(summary)
        return summary


__all__ = ["AngelBridge"]
