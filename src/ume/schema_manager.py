"""Utilities for managing multiple graph schema versions."""

from __future__ import annotations

from importlib import import_module, resources
from types import ModuleType
from typing import Dict, Iterable, Optional

from .graph_adapter import IGraphAdapter

from .graph_schema import GraphSchema, load_default_schema


class GraphSchemaManager:
    """Load and retrieve versioned :class:`GraphSchema` objects."""

    def __init__(self) -> None:
        self._schemas: Dict[str, GraphSchema] = {}
        self._protos: Dict[str, ModuleType] = {}
        self._default_version = load_default_schema().version
        self._load_available_schemas()
        self._load_available_protos()

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

    def _load_available_protos(self) -> None:
        try:
            from ume.protos import PROTO_MAP
        except Exception:  # pragma: no cover - optional during packaging
            return
        self._protos.update(PROTO_MAP)

    def available_versions(self) -> Iterable[str]:
        """Return available schema versions."""
        return self._schemas.keys()

    def get_proto(self, version: str) -> ModuleType:
        """Retrieve Protobuf module for a specific version."""
        if version not in self._protos:
            raise KeyError(f"Protobuf schema for version '{version}' not found")
        return self._protos[version]

    def get_schema(self, version: str | None = None) -> GraphSchema:
        """Retrieve schema for a specific version."""
        if version is None:
            version = self._default_version
        if version not in self._schemas:
            raise KeyError(f"Schema version '{version}' not found")
        return self._schemas[version]

    def register_schema(
        self, version: str, schema_path: str, proto_module: str
    ) -> None:
        """Register a new schema and protobuf mapping."""
        self._schemas[version] = GraphSchema.load(schema_path)
        self._protos[version] = import_module(proto_module)

    def upgrade_schema(
        self,
        old_version: str,
        new_version: str,
        graph: Optional[IGraphAdapter] = None,
    ) -> GraphSchema:
        """Upgrade stored data and return the requested schema."""

        self.get_schema(old_version)  # validate versions exist
        new_schema = self.get_schema(new_version)

        if graph is not None:
            if old_version == "1.0.0":
                for src, tgt, label, *_ in list(graph.get_all_edges()):
                    if label == "L":
                        graph.delete_edge(src, tgt, label)
                        graph.add_edge(src, tgt, "LINKS_TO")
                    elif label == "TO_DELETE":
                        graph.delete_edge(src, tgt, label)

            if new_version == "3.0.0":
                for src, tgt, label, attrs in list(graph.get_all_edges()):
                    if label == "NEW_LABEL":
                        graph.delete_edge(src, tgt, label)
                        graph.add_edge(src, tgt, "TAGGED_AS")
                    elif label == "HAS_PERMISSION":
                        graph.delete_edge(src, tgt, label)
                        perm_level = None
                        if isinstance(attrs, dict):
                            perm_level = attrs.get("permission_level")
                        else:
                            perm_level = attrs
                        new_label = "OWNED_BY" if perm_level == "editor" else "SHARED_WITH"
                        graph.add_edge(src, tgt, new_label, attrs)
                    elif label in {
                        "REMEMBERS",
                        "ASSOCIATED_WITH",
                        "CAUSES",
                        "LINKS_TO",
                        "CONNECTS_TO",
                        "RELATES_TO",
                    }:
                        graph.delete_edge(src, tgt, label)

        return new_schema


# Global manager instance used by ume internals
DEFAULT_SCHEMA_MANAGER = GraphSchemaManager()
