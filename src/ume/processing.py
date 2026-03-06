# src/ume/processing.py
from .event import Event
from .events.handlers import EVENT_HANDLER_REGISTRY
from .events.schema_resolution import resolve_active_schema
from .events.handlers.base import HandlerContext
from .graph_adapter import IGraphAdapter
from .graph_schema import load_default_schema
from .processing_errors import ProcessingError

DEFAULT_VERSION = load_default_schema().version


def apply_event_to_graph(
    event: Event, graph: IGraphAdapter, *, schema_version: str | None = None
) -> None:
    """Apply a validated event to the graph via the event handler registry."""
    handler = EVENT_HANDLER_REGISTRY.get(event.event_type)

    if handler is None:
        raise ProcessingError(
            f"Unknown event_type '{event.event_type}' for event: {event.event_id}"
        )

    resolved_schema_version = resolve_active_schema(
        {"metadata": {"schema_version": event.schema_version}},
        explicit_version=schema_version,
        default_version=DEFAULT_VERSION,
    ).active_version
    context = HandlerContext(event=event, graph=graph, schema_version=resolved_schema_version)
    handler.validate(context)
    handler.apply(context)
    handler.emit_listeners(context)
