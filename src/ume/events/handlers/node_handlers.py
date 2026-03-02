from __future__ import annotations

from ..._internal.listeners import get_registered_listeners
from ...processing_errors import ProcessingError
from .base import BaseEventHandler, HandlerContext
from .utils import add_tokens, require_str_field, validate_node_type_if_present


class CreateNodeHandler(BaseEventHandler):
    def validate(self, context: HandlerContext) -> None:
        event = context.event
        require_str_field(
            event.node_id,
            field_name="node_id",
            event=event,
            event_label="CREATE_NODE",
        )
        attributes = event.payload.get("attributes", {})
        if not isinstance(attributes, dict):
            raise ProcessingError(
                "'attributes' must be a dictionary for CREATE_NODE event, if provided. "
                f"Got: {type(attributes).__name__} for event: {event.event_id}"
            )
        validate_node_type_if_present(attributes, schema_version=context.schema_version)

    def apply(self, context: HandlerContext) -> None:
        event = context.event
        node_id = require_str_field(
            event.node_id,
            field_name="node_id",
            event=event,
            event_label="CREATE_NODE",
        )
        attributes = event.payload.get("attributes", {})
        assert isinstance(attributes, dict)
        add_tokens(attributes)
        context.graph.add_node(node_id, attributes)

    def emit_listeners(self, context: HandlerContext) -> None:
        event = context.event
        node_id = event.node_id
        attributes = event.payload.get("attributes", {})
        if isinstance(node_id, str) and isinstance(attributes, dict):
            for listener in get_registered_listeners():
                listener.on_node_created(node_id, attributes)


class UpdateNodeAttributesHandler(BaseEventHandler):
    def __init__(self, *, auto_archive: bool = False) -> None:
        self._auto_archive = auto_archive

    def validate(self, context: HandlerContext) -> None:
        event = context.event
        require_str_field(
            event.node_id,
            field_name="node_id",
            event=event,
            event_label="UPDATE_NODE_ATTRIBUTES",
        )
        if "attributes" not in event.payload:
            raise ProcessingError(
                "Missing 'attributes' key in payload for UPDATE_NODE_ATTRIBUTES event: "
                f"{event.event_id}"
            )
        attributes = event.payload["attributes"]
        if not isinstance(attributes, dict):
            raise ProcessingError(
                f"'attributes' must be a dictionary for UPDATE_NODE_ATTRIBUTES event: {event.event_id}"
            )

    def apply(self, context: HandlerContext) -> None:
        event = context.event
        node_id = require_str_field(
            event.node_id,
            field_name="node_id",
            event=event,
            event_label="UPDATE_NODE_ATTRIBUTES",
        )
        attributes = event.payload["attributes"]
        assert isinstance(attributes, dict)
        if self._auto_archive and "archived" not in attributes:
            attributes["archived"] = True
        if not attributes:
            raise ProcessingError(
                f"'attributes' dictionary cannot be empty for UPDATE_NODE_ATTRIBUTES event: {event.event_id}"
            )
        add_tokens(attributes)
        context.graph.update_node(node_id, attributes)

    def emit_listeners(self, context: HandlerContext) -> None:
        event = context.event
        node_id = event.node_id
        attributes = event.payload.get("attributes")
        if isinstance(node_id, str) and isinstance(attributes, dict):
            for listener in get_registered_listeners():
                listener.on_node_updated(node_id, attributes)


class RedactNodeHandler(BaseEventHandler):
    def validate(self, context: HandlerContext) -> None:
        event = context.event
        require_str_field(
            event.node_id,
            field_name="node_id",
            event=event,
            event_label="REDACT_NODE",
        )

    def apply(self, context: HandlerContext) -> None:
        event = context.event
        node_id = require_str_field(
            event.node_id,
            field_name="node_id",
            event=event,
            event_label="REDACT_NODE",
        )
        context.graph.redact_node(node_id)

    def emit_listeners(self, context: HandlerContext) -> None:
        return None
