"""Utilities for managing multiple graph schema versions."""

from __future__ import annotations

from importlib import resources
from typing import Dict, Iterable

from .graph_schema import GraphSchema, load_default_schema


class GraphSchemaManager:
    """Load and retrieve versioned :class:`GraphSchema` objects."""

    def __init__(self) -> None:
        self._schemas: Dict[str, GraphSchema] = {}
        self._load_available_schemas()

    def _load_available_schemas(self) -> None:
        pkg = resources.files("ume.schemas")
        for path in pkg.iterdir():
            name = path.name
            if name.startswith("graph_schema") and name.endswith(
                (".yaml", ".yml", ".json")
            ):
                schema = GraphSchema.load(str(path))
                self._schemas[schema.version] = schema

        # Ensure the default schema is always available even if its file name does not follow pattern
        default_schema = load_default_schema()
        self._schemas.setdefault(default_schema.version, default_schema)

    def available_versions(self) -> Iterable[str]:
        """Return available schema versions."""
        return self._schemas.keys()

    def get_schema(self, version: str) -> GraphSchema:
        """Retrieve schema for a specific version."""
        if version not in self._schemas:
            raise KeyError(f"Schema version '{version}' not found")
        return self._schemas[version]

    def upgrade_schema(self, old_version: str, new_version: str) -> GraphSchema:
        """Return the newer schema, placeholder for real migration logic."""
        # In a real implementation this would perform migrations. Here we simply
        # return the requested schema if available.
        old_schema = self.get_schema(old_version)  # noqa: F841 - might be used later
        return self.get_schema(new_version)


# Global manager instance used by ume internals
DEFAULT_SCHEMA_MANAGER = GraphSchemaManager()
