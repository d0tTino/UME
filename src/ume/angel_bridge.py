"""Angel Bridge service for generating daily summaries from recent events."""

from __future__ import annotations

from datetime import datetime, timezone
from .event_ledger import event_ledger
from .config import settings
from typing import Iterable, Dict, Any, List, Optional, TYPE_CHECKING
import importlib
import logging
import time

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from .client import UMEClient as UMEClientType  # noqa: F401

try:  # Optional Kafka dependency
    _module = importlib.import_module("ume.client")
    _UMEClientAny = getattr(_module, "UMEClient")
except Exception:  # pragma: no cover - confluent_kafka may be missing
    _UMEClientAny = None

UMEClient: Optional[type[UMEClientType]]
UMEClient = _UMEClientAny

logger = logging.getLogger(__name__)


class AngelBridge:
    """Consume recent events and emit a daily summary."""

    def __init__(self, lookback_hours: int | None = None) -> None:
        self.lookback_hours = lookback_hours or settings.ANGEL_BRIDGE_LOOKBACK_HOURS

    def consume_events(self) -> List[Dict[str, Any]]:
        """Return events from the last ``lookback_hours``.

        Events are fetched from the local :mod:`event_ledger`. If Kafka is
        configured and available, it will be used instead.
        """

        logger.debug("Consuming events for last %s hours", self.lookback_hours)
        cutoff = int(time.time()) - self.lookback_hours * 3600
        events: List[Dict[str, Any]] = []

        used_kafka = False
        if UMEClient is not None and settings.KAFKA_BOOTSTRAP_SERVERS:
            try:
                with UMEClient(settings) as client:
                    for event in client.consume_events(timeout=0.5):
                        if int(event.timestamp) >= cutoff:
                            events.append(
                                {
                                    "event_type": event.event_type,
                                    "timestamp": event.timestamp,
                                }
                            )
                used_kafka = True
            except Exception as exc:  # pragma: no cover - Kafka optional
                logger.warning("Kafka read failed: %s", exc)

        if not used_kafka:
            for _, data in event_ledger.range():
                ts = data.get("timestamp", 0)
                if ts >= cutoff:
                    events.append(data)

        return events

    def generate_summary(self, events: Iterable[Dict[str, Any]]) -> str:
        """Generate a text summary for the provided events."""
        counts: Dict[str, int] = {}
        for ev in events:
            etype = ev.get("event_type") or ev.get("type", "unknown")
            counts[etype] = counts.get(etype, 0) + 1

        today = datetime.now(timezone.utc).date()
        lines = [f"Summary for {today}:"]
        for etype, num in sorted(counts.items()):
            lines.append(f"{etype}: {num}")
        return "\n".join(lines)

    def emit_daily_summary(self) -> str:
        """Consume events and return the summary string."""
        events = self.consume_events()
        summary = self.generate_summary(events)
        logger.info(summary)
        return summary


__all__ = ["AngelBridge"]
