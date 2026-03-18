"""Compatibility facade for kernel event contracts."""

from .kernel.events import Event, EventError, EventType, parse_event

__all__ = ["Event", "EventError", "EventType", "parse_event"]
