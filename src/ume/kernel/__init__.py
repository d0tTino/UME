"""Kernel package exports for stable core boundaries.

The kernel contains foundational primitives shared by domain packs.
Domain packs must depend on this layer, while kernel code must not import domains.
"""

from .events import Event
from .graph_adapter import IGraphAdapter
from .ledger import EventLedger
from .policy import (
    PolicyContext,
    PolicyDecision,
    PolicyPipeline,
    build_default_policy_pipeline,
)
from .processing import DEFAULT_VERSION, ProcessingError, apply_event_to_graph

__all__ = [
    "Event",
    "EventLedger",
    "IGraphAdapter",
    "PolicyContext",
    "PolicyDecision",
    "PolicyPipeline",
    "ProcessingError",
    "DEFAULT_VERSION",
    "apply_event_to_graph",
    "build_default_policy_pipeline",
]
