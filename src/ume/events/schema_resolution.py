"""Central schema-version resolution for ingress, policy, and projection."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping





def _normalize_schema_version(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return None


@dataclass(frozen=True)
class SchemaResolution:
    active_version: str
    source: str


def resolve_active_schema(
    canonical_event: Mapping[str, Any],
    *,
    explicit_version: str | None = None,
    fallback_version: str | None = None,
    default_version: str,
) -> SchemaResolution:
    metadata = canonical_event.get("metadata") if isinstance(canonical_event, Mapping) else None
    metadata_schema = metadata.get("schema_version") if isinstance(metadata, Mapping) else None

    explicit = _normalize_schema_version(explicit_version)
    metadata_value = _normalize_schema_version(metadata_schema)
    fallback = _normalize_schema_version(fallback_version)

    if explicit is not None:
        return SchemaResolution(active_version=explicit, source="explicit")
    if metadata_value is not None:
        return SchemaResolution(active_version=metadata_value, source="metadata")
    if fallback is not None:
        return SchemaResolution(active_version=fallback, source="fallback")
    return SchemaResolution(active_version=default_version, source="default")


def annotate_canonical_schema(
    canonical_event: Mapping[str, Any],
    *,
    explicit_version: str | None = None,
    fallback_version: str | None = None,
    default_version: str,
) -> tuple[dict[str, Any], SchemaResolution]:
    resolution = resolve_active_schema(
        canonical_event,
        explicit_version=explicit_version,
        fallback_version=fallback_version,
        default_version=default_version,
    )
    annotated = deepcopy(dict(canonical_event))
    metadata = annotated.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        annotated["metadata"] = metadata
    metadata["schema_version"] = resolution.active_version
    metadata["schema_resolution_source"] = resolution.source
    return annotated, resolution


__all__ = ["SchemaResolution", "resolve_active_schema", "annotate_canonical_schema"]
