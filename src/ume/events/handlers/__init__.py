from __future__ import annotations

from ...event import EventType
from .base import EventHandler
from .edge_handlers import (
    CreateEdgeHandler,
    CreateOntologyRelationHandler,
    DeleteEdgeHandler,
    RedactEdgeHandler,
)
from .misc_handlers import NoOpEventHandler
from .node_handlers import CreateNodeHandler, RedactNodeHandler, UpdateNodeAttributesHandler

EVENT_HANDLER_REGISTRY: dict[EventType, EventHandler] = {
    EventType.CREATE_NODE: CreateNodeHandler(),
    EventType.RESEARCH_JOB_STARTED: CreateNodeHandler(),
    EventType.UPDATE_NODE_ATTRIBUTES: UpdateNodeAttributesHandler(),
    EventType.DOCUMENT_ARCHIVED: UpdateNodeAttributesHandler(auto_archive=True),
    EventType.CREATE_EDGE: CreateEdgeHandler(),
    EventType.DATA_SOURCE_QUERIED: CreateEdgeHandler(),
    EventType.ENTITY_DISCOVERED: CreateEdgeHandler(create_target_node_if_missing=True),
    EventType.CREATE_ONTOLOGY_RELATION: CreateOntologyRelationHandler(),
    EventType.DELETE_EDGE: DeleteEdgeHandler(),
    EventType.REDACT_NODE: RedactNodeHandler(),
    EventType.REDACT_EDGE: RedactEdgeHandler(),
    EventType.ANOMALY_DETECTED: NoOpEventHandler(),
}

__all__ = ["EVENT_HANDLER_REGISTRY", "EventHandler"]
