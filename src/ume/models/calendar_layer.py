"""Calendar layer node model and factory helpers."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from ..graph_schema import get_default_node_version

SCHEMA_VERSION = get_default_node_version("CalendarLayer")


@dataclass
class CalendarLayer:
    """Represents a calendar layer in the graph."""

    layer_id: str
    layer_name: str
    color: str
    schema_version: str = SCHEMA_VERSION


def create_calendar_layer(
    layer_name: str,
    color: str,
    *,
    layer_id: str | None = None,
) -> CalendarLayer:
    """Factory helper to build :class:`CalendarLayer` instances."""

    return CalendarLayer(
        layer_id=layer_id or str(uuid4()),
        layer_name=layer_name,
        color=color,
        schema_version=SCHEMA_VERSION,
    )
