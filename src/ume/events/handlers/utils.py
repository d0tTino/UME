from collections.abc import Iterable
from typing import Any

from ...kernel.events import Event
from ...processing_errors import ProcessingError
from ...schema_manager import DEFAULT_SCHEMA_MANAGER
from ...tokenization import tokenize


def add_tokens(attrs: dict[str, object]) -> None:
    """Tokenize textual fields and store the tokens list if any."""
    tokens: list[str] = []
    for key in ("name", "text", "content"):
        val = attrs.get(key)
        if isinstance(val, str):
            tokens.extend(tokenize(val))
    if tokens:
        attrs["tokens"] = tokens


def require_str_field(value: object, *, field_name: str, event: Event, event_label: str) -> str:
    if not value:
        raise ProcessingError(
            f"Missing '{field_name}' in event for {event_label} event: {event.event_id}"
        )
    if not isinstance(value, str):
        raise ProcessingError(
            f"'{field_name}' must be a string for {event_label} event: {event.event_id}"
        )
    return value


def require_edge_fields(event: Event, *, event_label: str) -> tuple[str, str, str]:
    source_node_id = event.node_id
    target_node_id = event.target_node_id
    label = event.label
    if not (
        isinstance(source_node_id, str)
        and isinstance(target_node_id, str)
        and isinstance(label, str)
    ):
        raise ProcessingError(
            f"Invalid event structure for {event_label}: source_node_id (event.node_id), "
            f"target_node_id, and label must be strings and present. Event ID: {event.event_id}"
        )
    return source_node_id, target_node_id, label


def validate_node_type_if_present(attributes: dict[str, object], *, schema_version: str) -> None:
    node_type = attributes.get("type")
    if node_type is None:
        return
    schema = DEFAULT_SCHEMA_MANAGER.get_schema(schema_version)
    schema.validate_node_type(str(node_type))


def read_edge_attributes(event: Event) -> dict[str, Any] | None:
    raw_edge_attrs = event.payload.get("attributes")
    if raw_edge_attrs is not None and not isinstance(raw_edge_attrs, dict):
        raise ProcessingError(
            f"'attributes' must be a dictionary for {event.event_type} event: {event.event_id}"
        )
    return dict(raw_edge_attrs) if isinstance(raw_edge_attrs, dict) else None


def validate_permission_level(
    *,
    edge_attrs: dict[str, Any] | None,
    label: str,
    permission_level_values: Iterable[str],
    default_permission_level: str | None,
) -> None:
    if edge_attrs is None:
        return
    permission_level = edge_attrs.get("permission_level")
    if permission_level is None:
        return
    if not isinstance(permission_level, str) or not permission_level:
        raise ProcessingError(
            "permission_level must be a non-empty string when provided for permissioned edges"
        )

    accepted_levels = set(permission_level_values)
    if not accepted_levels and default_permission_level is not None:
        accepted_levels.add(default_permission_level)
    if accepted_levels and permission_level not in accepted_levels:
        raise ProcessingError(
            f"Invalid permission_level '{permission_level}' for edge label '{label}'"
        )
