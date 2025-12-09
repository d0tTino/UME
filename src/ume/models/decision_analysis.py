"""Decision analysis model and factory helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid

from ..graph_schema import get_default_node_version

SCHEMA_VERSION = get_default_node_version("DecisionAnalysis")


@dataclass
class DecisionAnalysis:
    """Represents the analysis of a decision query."""

    analysis_id: str
    query: str
    created_at: datetime
    schema_version: str = SCHEMA_VERSION


def create_decision_analysis(
    query: str,
    *,
    analysis_id: str | None = None,
) -> DecisionAnalysis:
    """Factory helper to build :class:`DecisionAnalysis` instances."""

    return DecisionAnalysis(
        analysis_id=analysis_id or str(uuid.uuid4()),
        query=query,
        created_at=datetime.utcnow(),
        schema_version=SCHEMA_VERSION,
    )
