"""Graph schema utilities with versioned node and edge definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from typing import Dict, NoReturn
import json
import yaml


@dataclass
class Property:
    """Representation of a property within a node type."""

    name: str
    version: str
    permission_level: str | None = None
    permission_level_values: tuple[str, ...] = ()


@dataclass
class NodeType:
    """Representation of a node type within the graph schema."""

    name: str
    version: str
    permission_level: str | None = None
    permission_level_values: tuple[str, ...] = ()
    properties: Dict[str, Property] = field(default_factory=dict)


@dataclass
class EdgeLabel:
    """Representation of an edge label within the graph schema."""

    label: str
    version: str
    permission_level: str | None = None
    permission_level_values: tuple[str, ...] = ()


@dataclass
class GraphSchema:
    """Container for node and edge definitions."""

    version: str = "0.0.0"
    node_types: Dict[str, NodeType] = field(default_factory=dict)
    edge_labels: Dict[str, EdgeLabel] = field(default_factory=dict)

    @staticmethod
    def load(path: str) -> "GraphSchema":
        """Load schema definitions from a JSON or YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            if path.endswith((".yaml", ".yml")):
                data = yaml.safe_load(f)
            else:
                data = json.load(f)

        def _parse_permission(
            value: object, context: str
        ) -> tuple[str | None, tuple[str, ...]]:
            def _error(message: str) -> NoReturn:
                from .processing import ProcessingError

                raise ProcessingError(message)

            if value is None:
                return None, ()
            if isinstance(value, str):
                value_str = str(value)
                return value_str, (value_str,)
            if isinstance(value, dict):
                default = value.get("default")
                accepted = value.get("accepted_values")
                default_str = str(default) if default is not None else None
                if accepted is None:
                    values: list[str] = []
                elif isinstance(accepted, (list, tuple, set)):
                    values = [str(v) for v in accepted]
                else:
                    _error(
                        f"{context} permission_level accepted_values must be a sequence of strings"
                    )
                if default_str is not None and default_str not in values:
                    values.append(default_str)
                values = list(dict.fromkeys(values))
                return default_str, tuple(values)
            _error(f"{context} permission_level must be a string or mapping")

        node_types = {}
        for name, info in data.get("node_types", {}).items():
            if not isinstance(info, dict):
                from .processing import ProcessingError

                raise ProcessingError(
                    f"Node type '{name}' must be a mapping",
                )
            properties_data = info.get("properties")
            if properties_data is None or not isinstance(properties_data, dict):
                from .processing import ProcessingError

                raise ProcessingError(
                    f"Node type '{name}' must include a 'properties' mapping",
                )
            properties = {}
            for prop_name, prop_info in properties_data.items():
                if not isinstance(prop_info, dict):
                    from .processing import ProcessingError

                    raise ProcessingError(
                        f"Property '{prop_name}' for node type '{name}' must be a mapping",
                    )
                prop_perm, prop_perm_values = _parse_permission(
                    prop_info.get("permission_level"),
                    f"Property '{prop_name}' for node type '{name}'",
                )
                properties[prop_name] = Property(
                    name=prop_name,
                    version=str(prop_info.get("version", "0.0.0")),
                    permission_level=prop_perm,
                    permission_level_values=prop_perm_values,
                )
            node_perm, node_perm_values = _parse_permission(
                info.get("permission_level"), f"Node type '{name}'"
            )
            node_types[name] = NodeType(
                name=name,
                version=str(info.get("version", "0.0.0")),
                permission_level=node_perm,
                permission_level_values=node_perm_values,
                properties=properties,
            )
        edge_labels: Dict[str, EdgeLabel] = {}
        for label, info in data.get("edge_labels", {}).items():
            if not isinstance(info, dict):
                from .processing import ProcessingError

                raise ProcessingError(
                    f"Edge label '{label}' must be a mapping",
                )
            edge_perm, edge_perm_values = _parse_permission(
                info.get("permission_level"), f"Edge label '{label}'"
            )
            edge_labels[label] = EdgeLabel(
                label=label,
                version=str(info.get("version", "0.0.0")),
                permission_level=edge_perm,
                permission_level_values=edge_perm_values,
            )
        version = str(data.get("version", "0.0.0"))
        return GraphSchema(
            version=version, node_types=node_types, edge_labels=edge_labels
        )

    @classmethod
    def load_default(cls) -> "GraphSchema":
        """Load the built-in schema packaged with ume."""
        schema_path = resources.files("ume.schemas").joinpath("graph_schema_v3.yaml")
        return cls.load(str(schema_path))

    def validate_node_type(self, node_type: str) -> None:
        """Validate that the given node type exists in the schema."""
        if node_type not in self.node_types:
            from .processing import ProcessingError

            raise ProcessingError(f"Unknown node type '{node_type}'")

    def validate_edge_label(self, label: str) -> None:
        """Validate that the given edge label exists in the schema."""
        if label not in self.edge_labels:
            from .processing import ProcessingError

            raise ProcessingError(f"Unknown edge label '{label}'")

    def get_edge_version(self, label: str) -> str:
        """Return the version string for the specified edge label."""
        self.validate_edge_label(label)
        return self.edge_labels[label].version

    def validate_node_property(self, node_type: str, property_name: str) -> None:
        """Validate that a property exists for a given node type."""
        self.validate_node_type(node_type)
        if property_name not in self.node_types[node_type].properties:
            from .processing import ProcessingError

            raise ProcessingError(
                f"Unknown property '{property_name}' for node type '{node_type}'"
            )


def load_default_schema() -> GraphSchema:
    """Helper to load the default graph schema."""
    return GraphSchema.load_default()


# Load schema on module import for convenience
DEFAULT_SCHEMA = load_default_schema()


def get_default_node_version(node_type: str) -> str:
    """Return the version string for a node type in :data:`DEFAULT_SCHEMA`."""

    node_def = DEFAULT_SCHEMA.node_types.get(node_type)
    if node_def is None:
        return DEFAULT_SCHEMA.version
    return node_def.version


def get_default_edge_version(label: str) -> str:
    """Return the version string for an edge label in :data:`DEFAULT_SCHEMA`."""

    edge_def = DEFAULT_SCHEMA.edge_labels.get(label)
    if edge_def is None:
        return DEFAULT_SCHEMA.version
    return edge_def.version
