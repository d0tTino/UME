"""Kernel processing orchestration contracts."""

from __future__ import annotations

from importlib import import_module

from .events import Event
from .graph_adapter import IGraphAdapter


class ProcessingError(ValueError):
    """Custom exception for event processing errors."""


DEFAULT_VERSION = "1.0.0"


def apply_event_to_graph(
    event: Event, graph: IGraphAdapter, *, schema_version: str | None = None
) -> None:
    """Apply a validated event to the graph via the event handler registry."""
    handlers = import_module("ume.events.handlers")
    schema_resolution = import_module("ume.events.schema_resolution")
    handler_base = import_module("ume.events.handlers.base")
    graph_schema = import_module("ume.graph_schema")

    default_version = graph_schema.load_default_schema().version
    handler = handlers.EVENT_HANDLER_REGISTRY.get(event.event_type)

    if handler is None:
        raise ProcessingError(
            f"Unknown event_type '{event.event_type}' for event: {event.event_id}"
        )

    resolved_schema_version = schema_resolution.resolve_active_schema(
        {"metadata": {"schema_version": event.schema_version}},
        explicit_version=schema_version,
        default_version=default_version,
    ).active_version
    context = handler_base.HandlerContext(event=event, graph=graph, schema_version=resolved_schema_version)
    handler.validate(context)
    handler.apply(context)
    handler.emit_listeners(context)


__all__ = ["DEFAULT_VERSION", "ProcessingError", "apply_event_to_graph"]
