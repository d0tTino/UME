# src/ume/processing.py
from .event import Event
from .events.handlers import EVENT_HANDLER_REGISTRY
from .events.handlers.base import HandlerContext
from .graph_adapter import IGraphAdapter
from .graph_schema import load_default_schema
from .processing_errors import ProcessingError

DEFAULT_VERSION = load_default_schema().version


def apply_event_to_graph(
    event: Event, graph: IGraphAdapter, *, schema_version: str = DEFAULT_VERSION
) -> None:
    """Apply a validated event to the graph via the event handler registry."""
    handler = EVENT_HANDLER_REGISTRY.get(event.event_type)

    if handler is None:
        raise ProcessingError(
            f"Unknown event_type '{event.event_type}' for event: {event.event_id}"
        )

    context = HandlerContext(event=event, graph=graph, schema_version=schema_version)
    handler.validate(context)
    handler.apply(context)
    handler.emit_listeners(context)
