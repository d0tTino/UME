"""Proposed action node model and factory helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class ProposedAction:
    """Represents an action that can be taken in response to a decision analysis."""

    action_id: str
    description: str
    created_at: datetime = field(default_factory=datetime.utcnow)


def create_proposed_action(
    description: str,
    *,
    action_id: str | None = None,
    created_at: datetime | None = None,
) -> ProposedAction:
    """Factory helper to build :class:`ProposedAction` instances."""

    return ProposedAction(
        action_id=action_id or str(uuid.uuid4()),
        description=description,
        created_at=created_at or datetime.utcnow(),
    )
