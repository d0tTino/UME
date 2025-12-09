"""Decision node model and factory helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import uuid

from ..graph_schema import get_default_node_version

SCHEMA_VERSION = get_default_node_version("Decision")


@dataclass
class Decision:
    """Represents a decision in the graph."""

    id: str
    description: str
    made_by: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    schema_version: str = SCHEMA_VERSION


def create_decision(
    description: str,
    *,
    made_by: str | None = None,
    decision_id: str | None = None,
    timestamp: datetime | None = None,
) -> Decision:
    """Factory helper to build :class:`Decision` instances."""

    return Decision(
        id=decision_id or str(uuid.uuid4()),
        description=description,
        made_by=made_by,
        timestamp=timestamp or datetime.utcnow(),
    )
