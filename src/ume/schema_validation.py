"""Validation helpers for ensuring graph mutations match the active schema."""

from __future__ import annotations

from typing import Mapping

from .graph_schema import GraphSchema
from .processing import ProcessingError
from .schema_manager import DEFAULT_SCHEMA_MANAGER


def _get_schema(schema: GraphSchema | None = None) -> GraphSchema:
    if schema is not None:
        return schema
    return DEFAULT_SCHEMA_MANAGER.get_schema()


def validate_node_attributes(
    attrs: Mapping[str, object], schema: GraphSchema | None = None
) -> str:
    """Validate a node payload against the provided :class:`GraphSchema`.

    Returns the expected schema version for the node type so callers can apply
    it to storage writes.
    """

    active_schema = _get_schema(schema)
    node_type = attrs.get("type") if isinstance(attrs, Mapping) else None
    if not isinstance(node_type, str) or not node_type:
        raise ProcessingError("Node attributes must include a non-empty 'type'")

    node_def = active_schema.node_types.get(node_type)
    if node_def is None:
        raise ProcessingError(f"Unknown node type '{node_type}'")

    missing = [prop for prop in node_def.properties if prop not in attrs]
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ProcessingError(
            f"Missing required properties for node type '{node_type}': {missing_list}"
        )

    expected_version = node_def.version
    provided_version = attrs.get("schema_version") if isinstance(attrs, Mapping) else None
    if provided_version not in (None, expected_version):
        raise ProcessingError(
            "schema_version does not match the active schema for node type "
            f"'{node_type}' (expected '{expected_version}')"
        )

    return expected_version


def validate_edge(
    label: str,
    attrs: Mapping[str, object] | None = None,
    schema_version: str | None = None,
    schema: GraphSchema | None = None,
) -> str:
    """Validate an edge against the active schema and return its version."""

    active_schema = _get_schema(schema)
    if not isinstance(label, str) or not label:
        raise ProcessingError("Edge label must be a non-empty string")

    edge_def = active_schema.edge_labels.get(label)
    if edge_def is None:
        raise ProcessingError(f"Unknown edge label '{label}'")

    expected_version = edge_def.version
    provided_version = schema_version
    if provided_version not in (None, expected_version):
        raise ProcessingError(
            "schema_version does not match the active schema for edge label "
            f"'{label}' (expected '{expected_version}')"
        )

    if attrs is not None and isinstance(attrs, Mapping):
        perm_level = attrs.get("permission_level")
        if perm_level is not None and edge_def.permission_level_values:
            if perm_level not in edge_def.permission_level_values:
                raise ProcessingError(
                    f"Invalid permission_level '{perm_level}' for edge label '{label}'"
                )

    return expected_version


__all__ = [
    "validate_edge",
    "validate_node_attributes",
]
