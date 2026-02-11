from __future__ import annotations

from ..._internal.listeners import get_registered_listeners
from ...processing_errors import ProcessingError
from ...schema_manager import DEFAULT_SCHEMA_MANAGER
from .base import BaseEventHandler, HandlerContext
from .utils import add_tokens, read_edge_attributes, require_edge_fields, validate_permission_level


class CreateEdgeHandler(BaseEventHandler):
    def __init__(self, *, create_target_node_if_missing: bool = False) -> None:
        self._create_target_node_if_missing = create_target_node_if_missing

    def validate(self, context: HandlerContext) -> None:
        event = context.event
        _, _, label = require_edge_fields(event, event_label="CREATE_EDGE")
        schema = DEFAULT_SCHEMA_MANAGER.get_schema(context.schema_version)
        schema.validate_edge_label(label)

        edge_attrs = read_edge_attributes(event)
        edge_def = schema.edge_labels.get(label)
        if edge_def:
            validate_permission_level(
                edge_attrs=edge_attrs,
                label=label,
                permission_level_values=edge_def.permission_level_values,
                default_permission_level=edge_def.permission_level,
            )

    def apply(self, context: HandlerContext) -> None:
        event = context.event
        source_node_id, target_node_id, label = require_edge_fields(
            event, event_label="CREATE_EDGE"
        )

        schema = DEFAULT_SCHEMA_MANAGER.get_schema(context.schema_version)
        edge_attrs = read_edge_attributes(event)
        edge_def = schema.edge_labels.get(label)
        edge_schema_version = edge_def.version if edge_def else schema.version

        if self._create_target_node_if_missing and not context.graph.node_exists(target_node_id):
            node_attrs = dict(edge_attrs) if edge_attrs is not None else {}
            add_tokens(node_attrs)
            context.graph.add_node(target_node_id, node_attrs)
            for listener in get_registered_listeners():
                listener.on_node_created(target_node_id, node_attrs)

        context.graph.add_edge(
            source_node_id,
            target_node_id,
            label,
            edge_attrs,
            schema_version=edge_schema_version,
        )

    def emit_listeners(self, context: HandlerContext) -> None:
        event = context.event
        source_node_id, target_node_id, label = require_edge_fields(
            event, event_label="CREATE_EDGE"
        )
        for listener in get_registered_listeners():
            listener.on_edge_created(source_node_id, target_node_id, label)


class CreateOntologyRelationHandler(BaseEventHandler):
    def validate(self, context: HandlerContext) -> None:
        source_node_id = context.event.node_id
        target_node_id = context.event.target_node_id
        label = context.event.label
        if not (
            isinstance(source_node_id, str)
            and isinstance(target_node_id, str)
            and isinstance(label, str)
        ):
            raise ProcessingError(
                "Invalid event structure for CREATE_ONTOLOGY_RELATION: source_node_id, "
                f"target_node_id, and label must be strings. Event ID: {context.event.event_id}"
            )
        schema = DEFAULT_SCHEMA_MANAGER.get_schema(context.schema_version)
        schema.validate_edge_label(label)

    def apply(self, context: HandlerContext) -> None:
        source_node_id = context.event.node_id
        target_node_id = context.event.target_node_id
        label = context.event.label
        assert isinstance(source_node_id, str)
        assert isinstance(target_node_id, str)
        assert isinstance(label, str)
        context.graph.add_edge(source_node_id, target_node_id, label)

    def emit_listeners(self, context: HandlerContext) -> None:
        source_node_id = context.event.node_id
        target_node_id = context.event.target_node_id
        label = context.event.label
        if isinstance(source_node_id, str) and isinstance(target_node_id, str) and isinstance(label, str):
            for listener in get_registered_listeners():
                listener.on_edge_created(source_node_id, target_node_id, label)


class DeleteEdgeHandler(BaseEventHandler):
    def validate(self, context: HandlerContext) -> None:
        require_edge_fields(context.event, event_label="DELETE_EDGE")

    def apply(self, context: HandlerContext) -> None:
        source_node_id, target_node_id, label = require_edge_fields(
            context.event, event_label="DELETE_EDGE"
        )
        context.graph.delete_edge(source_node_id, target_node_id, label)

    def emit_listeners(self, context: HandlerContext) -> None:
        source_node_id, target_node_id, label = require_edge_fields(
            context.event, event_label="DELETE_EDGE"
        )
        for listener in get_registered_listeners():
            listener.on_edge_deleted(source_node_id, target_node_id, label)
