"""Topic routing utilities for canonical events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..config import settings

_POLICY_DENY_RESULTS = {"deny", "denied", "reject", "rejected", "blocked"}


@dataclass(frozen=True)
class RouterConfig:
    """Destination topics used by the stream processor."""

    node_topic: str
    edge_topic: str
    default_topic: str
    dead_letter_topic: str


@dataclass(frozen=True)
class RoutingDecision:
    """Result of applying routing semantics to one canonical event."""

    topic: str
    family: str
    schema_version: str | None
    policy_result: str | None
    reason: str


def router_config_from_settings() -> RouterConfig:
    """Build router configuration from process settings."""

    return RouterConfig(
        node_topic=settings.KAFKA_NODE_TOPIC,
        edge_topic=settings.KAFKA_EDGE_TOPIC,
        default_topic=settings.KAFKA_ROUTING_FALLBACK_TOPIC,
        dead_letter_topic=settings.KAFKA_ROUTING_DEAD_LETTER_TOPIC,
    )


def route_event(
    canonical_event: Mapping[str, Any], config: RouterConfig
) -> RoutingDecision:
    """Compute destination topic from canonical metadata + schema hints."""

    metadata = canonical_event.get("metadata")
    graph = canonical_event.get("graph")
    if not isinstance(metadata, Mapping):
        metadata = {}
    if not isinstance(graph, Mapping):
        graph = {}

    family = _type_family(metadata, graph)
    schema_version = _string_value(metadata.get("schema_version"))
    policy_result = _policy_result(metadata)

    if policy_result in _POLICY_DENY_RESULTS:
        return RoutingDecision(
            topic=config.dead_letter_topic,
            family=family,
            schema_version=schema_version,
            policy_result=policy_result,
            reason="policy_denied",
        )

    schema_topic = _schema_topic(metadata)
    if schema_topic:
        return RoutingDecision(
            topic=schema_topic,
            family=family,
            schema_version=schema_version,
            policy_result=policy_result,
            reason="schema_topic",
        )

    if family == "edge":
        return RoutingDecision(
            topic=config.edge_topic,
            family=family,
            schema_version=schema_version,
            policy_result=policy_result,
            reason="edge_family",
        )

    if family == "node":
        return RoutingDecision(
            topic=config.node_topic,
            family=family,
            schema_version=schema_version,
            policy_result=policy_result,
            reason="node_family",
        )

    return RoutingDecision(
        topic=config.default_topic,
        family=family,
        schema_version=schema_version,
        policy_result=policy_result,
        reason="fallback",
    )


def _schema_topic(metadata: Mapping[str, Any]) -> str | None:
    direct_topic = _string_value(metadata.get("destination_topic") or metadata.get("topic"))
    if direct_topic:
        return direct_topic

    schema_meta = metadata.get("schema")
    if isinstance(schema_meta, Mapping):
        return _string_value(schema_meta.get("topic"))

    schema_meta = metadata.get("schema_metadata")
    if isinstance(schema_meta, Mapping):
        return _string_value(schema_meta.get("topic"))

    return None


def _policy_result(metadata: Mapping[str, Any]) -> str | None:
    policy_result = _string_value(metadata.get("policy_result"))
    if policy_result:
        return policy_result.lower()

    policy_data = metadata.get("policy")
    if isinstance(policy_data, Mapping):
        nested = _string_value(policy_data.get("result"))
        if nested:
            return nested.lower()

    return None


def _type_family(metadata: Mapping[str, Any], graph: Mapping[str, Any]) -> str:
    metadata_family = _string_value(metadata.get("type_family"))
    if metadata_family:
        return metadata_family.lower()

    event_type = _string_value(metadata.get("event_type"))
    event_type_upper = event_type.upper() if event_type else ""

    has_node_id = _string_value(graph.get("node_id")) is not None
    has_target_node_id = _string_value(graph.get("target_node_id")) is not None
    has_label = _string_value(graph.get("label")) is not None

    if has_node_id and has_target_node_id and has_label:
        return "edge"
    if has_node_id:
        return "node"

    if any(keyword in event_type_upper for keyword in ("EDGE", "RELATION", "LINK")):
        return "edge"
    if any(keyword in event_type_upper for keyword in ("NODE", "DOCUMENT", "ENTITY", "RESEARCH")):
        return "node"

    return "unknown"


def _string_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized if normalized else None
