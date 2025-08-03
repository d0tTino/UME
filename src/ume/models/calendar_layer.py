"""Calendar layer model and factory helpers."""

from __future__ import annotations

from dataclasses import dataclass
import uuid


@dataclass
class CalendarLayer:
    """Represents a calendar layer in the graph."""

    layer_id: str
    layer_name: str
    color: str


def create_calendar_layer(
    layer_name: str,
    color: str,
    *,
    layer_id: str | None = None,
) -> CalendarLayer:
    """Factory helper to build :class:`CalendarLayer` instances."""

    return CalendarLayer(
        layer_id=layer_id or str(uuid.uuid4()),
        layer_name=layer_name,
        color=color,
    )
