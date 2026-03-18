"""Kernel package exports for stable core boundaries."""

from typing import Any

from .events import Event
from .graph_adapter import IGraphAdapter
from .policy import PolicyContext, PolicyDecision, build_default_policy_pipeline
from .processing import DEFAULT_VERSION, ProcessingError, apply_event_to_graph

PolicyPipeline: Any
EventLedger: Any


def __getattr__(name: str):
    if name == "PolicyPipeline":
        from .policy import PolicyPipeline

        return PolicyPipeline
    if name == "EventLedger":
        from .ledger import EventLedger

        return EventLedger
    raise AttributeError(name)


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
