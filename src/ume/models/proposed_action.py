"""Proposed action node model and factory helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
import uuid


SCHEMA_VERSION = "3.0.0"


@dataclass
class ProposedAction:
    """Represents an action that can be taken in response to a decision analysis.

    Attributes:
        action_id: Unique identifier for the proposed action.
        description: Human-readable summary of the action.
        rank: Ordering of this action relative to others.
        is_optimal: Whether this action is considered the best option.
        outcome_metrics: Expected outcome metrics keyed by name.
        schema_version: Version of the ProposedAction schema.
    """

    action_id: str
    description: str
    rank: int = 0
    is_optimal: bool = False
    outcome_metrics: dict[str, float] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION


def create_proposed_action(
    description: str,
    *,
    action_id: str | None = None,
    rank: int = 0,
    is_optimal: bool = False,
    outcome_metrics: dict[str, float] | None = None,
) -> ProposedAction:
    """Factory helper to build :class:`ProposedAction` instances."""

    return ProposedAction(
        action_id=action_id or str(uuid.uuid4()),
        description=description,
        rank=rank,
        is_optimal=is_optimal,
        outcome_metrics=outcome_metrics or {},
    )
