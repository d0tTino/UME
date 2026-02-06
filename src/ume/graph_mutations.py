"""Schema-aware helpers for graph creation operations."""

from __future__ import annotations

from typing import Any, Mapping

from .graph_adapter import IGraphAdapter
from .graph_schema import DEFAULT_SCHEMA, GraphSchema
from .processing import ProcessingError
from .schema_validation import validate_edge, validate_node_attributes


def add_node_with_schema_validation(
    graph: IGraphAdapter,
    node_id: str,
    attrs: Mapping[str, Any],
    *,
    schema: GraphSchema | None = None,
) -> dict[str, Any]:
    """Validate a node payload and add it with the matching schema version."""

    node_attrs = dict(attrs)
    expected_version = validate_node_attributes(node_attrs, schema=schema or DEFAULT_SCHEMA)
    node_attrs["schema_version"] = expected_version
    graph.add_node(node_id, node_attrs)
    return node_attrs


def add_edge_with_schema_validation(
    graph: IGraphAdapter,
    source_node_id: str,
    target_node_id: str,
    label: str,
    attrs: Mapping[str, Any] | None = None,
    *,
    schema: GraphSchema | None = None,
    schema_version: str | None = None,
) -> str:
    """Validate an edge payload and add it with the matching schema version."""

    edge_attrs = dict(attrs) if attrs is not None else None
    expected_version = validate_edge(
        label,
        edge_attrs,
        schema_version=schema_version,
        schema=schema or DEFAULT_SCHEMA,
    )
    if schema_version is not None and schema_version != expected_version:
        raise ProcessingError(
            "schema_version does not match the active schema for edge label "
            f"'{label}' (expected '{expected_version}')"
        )
    graph.add_edge(
        source_node_id,
        target_node_id,
        label,
        edge_attrs,
        schema_version=expected_version,
    )
    return expected_version


__all__ = ["add_edge_with_schema_validation", "add_node_with_schema_validation"]

