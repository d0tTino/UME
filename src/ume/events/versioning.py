"""Schema-version resolution for event ingestion."""

from __future__ import annotations

from typing import Any, Mapping


def normalize_schema_version(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return None


def resolve_schema_version(
    canonical_event: Mapping[str, Any],
    *,
    explicit_version: str | None = None,
    fallback_version: str | None = None,
    default_version: str,
) -> str:
    metadata = canonical_event.get("metadata") if isinstance(canonical_event, Mapping) else None
    metadata_schema = None
    if isinstance(metadata, Mapping):
        metadata_schema = metadata.get("schema_version")

    return (
        normalize_schema_version(explicit_version)
        or normalize_schema_version(metadata_schema)
        or normalize_schema_version(fallback_version)
        or default_version
    )
