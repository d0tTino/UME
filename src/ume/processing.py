"""Compatibility facade for kernel processing contracts."""

from .kernel.processing import DEFAULT_VERSION, ProcessingError, apply_event_to_graph

__all__ = ["DEFAULT_VERSION", "ProcessingError", "apply_event_to_graph"]
