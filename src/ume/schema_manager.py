"""Utilities for managing multiple graph schema versions."""

from __future__ import annotations

from importlib import resources
from typing import Dict, Iterable, Optional

from .graph_adapter import IGraphAdapter

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

    def upgrade_schema(
        self,
        old_version: str,
        new_version: str,
        graph: Optional[IGraphAdapter] = None,
    ) -> GraphSchema:
        """Upgrade stored data and return the requested schema."""

        self.get_schema(old_version)  # validate versions exist
        new_schema = self.get_schema(new_version)

        if graph is not None and old_version == "1.0.0" and new_version == "2.0.0":
            for src, tgt, label in list(graph.get_all_edges()):
                if label == "L":
                    graph.delete_edge(src, tgt, label)
                    graph.add_edge(src, tgt, "LINKS_TO")
                elif label == "TO_DELETE":
                    graph.delete_edge(src, tgt, label)

        return new_schema


# Global manager instance used by ume internals
DEFAULT_SCHEMA_MANAGER = GraphSchemaManager()
