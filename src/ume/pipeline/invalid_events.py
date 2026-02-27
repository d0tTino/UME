"""Shared invalid-event outcomes and ledger serialization helpers."""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping

from ..event import Event
from ..events.contract import canonical_to_camel_dict
from ..policy.pipeline import PolicyDecision
from .core import PipelineOutcome


class InvalidEventOutcome(str, Enum):
    REJECT = "reject"
    QUARANTINE = "quarantine"
    DEAD_LETTER = "dead_letter"


def outcome_for_policy_decision(decision: PolicyDecision) -> InvalidEventOutcome:
    """Map policy decisions to explicit invalid-event outcomes."""

    if decision == PolicyDecision.QUARANTINE:
        return InvalidEventOutcome.QUARANTINE
    if decision == PolicyDecision.DENY:
        return InvalidEventOutcome.DEAD_LETTER
    return InvalidEventOutcome.REJECT


def build_rejected_event_ledger_entry(
    *,
    outcome: InvalidEventOutcome,
    reason: str,
    source: str,
    canonical: Mapping[str, Any] | None,
    event: Event | None,
) -> dict[str, Any]:
    """Build a deterministic rejected-event ledger payload."""

    timestamp = 0
    if event is not None and isinstance(event.timestamp, int):
        timestamp = event.timestamp
    elif isinstance(canonical, Mapping):
        metadata = canonical.get("metadata")
        if isinstance(metadata, Mapping) and isinstance(metadata.get("timestamp"), int):
            timestamp = metadata["timestamp"]

    original = canonical_to_camel_dict(canonical) if canonical is not None else None
    return {
        "eventType": "REJECTED_EVENT",
        "timestamp": timestamp,
        "payload": {
            "outcome": outcome.value,
            "reason": reason,
            "source": source,
            "original_event": original,
            "original_event_id": event.event_id if event is not None else None,
            "original_event_type": event.event_type if event is not None else None,
        },
    }



def outcome_for_pipeline_outcome(outcome: PipelineOutcome) -> InvalidEventOutcome:
    if outcome == PipelineOutcome.QUARANTINED:
        return InvalidEventOutcome.QUARANTINE
    if outcome == PipelineOutcome.REJECTED:
        return InvalidEventOutcome.REJECT
    if outcome == PipelineOutcome.REDACTED:
        return InvalidEventOutcome.REJECT
    return InvalidEventOutcome.REJECT
