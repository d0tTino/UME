"""Contract models for real-time graph projection streams."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class GraphDigestEvent(BaseModel):
    """Compact graph mutation digest emitted by the real-time stream."""

    offset: int
    event_id: str | None = None
    event_type: str
    source_service: str | None = None
    schema_version: str | None = None
    timestamp: int | None = None
    node_id: str | None = None
    target_node_id: str | None = None
    label: str | None = None
    payload_hash: str


class GraphDigestControlEvent(BaseModel):
    """Out-of-band stream control events (heartbeat/backpressure)."""

    kind: Literal["heartbeat", "backpressure"]
    cursor_offset: int
    dropped_events: int = 0


class DashboardDigestEvent(BaseModel):
    """Sanitized dashboard state emitted for real-time UI updates."""

    cursor_offset: int
    stats: dict[str, int]
    recent_events: list[GraphDigestEvent]
    redacted_count: int
