"""Decision analysis model and factory helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class DecisionAnalysis:
    """Represents the analysis of a decision query."""

    analysis_id: str
    query: str
    created_at: datetime = field(default_factory=datetime.utcnow)


def create_decision_analysis(
    query: str,
    *,
    analysis_id: str | None = None,
    created_at: datetime | None = None,
) -> DecisionAnalysis:
    """Factory helper to build :class:`DecisionAnalysis` instances."""

    return DecisionAnalysis(
        analysis_id=analysis_id or str(uuid.uuid4()),
        query=query,
        created_at=created_at or datetime.utcnow(),
    )
