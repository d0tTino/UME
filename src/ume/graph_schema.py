"""Graph schema utilities with versioned node and edge definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from typing import Dict
import json
try:  # optional dependency
    import yaml
except Exception:  # pragma: no cover - optional dependency missing
    yaml = None  # type: ignore


@dataclass
class NodeType:
    """Representation of a node type within the graph schema."""

    name: str
    version: str


@dataclass
class EdgeLabel:
    """Representation of an edge label within the graph schema."""

    label: str
    version: str


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
                if yaml is None:
                    raise ImportError("PyYAML is required to load YAML schemas")
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
        node_types = {
            name: NodeType(name=name, version=str(info.get("version", "0.0.0")))
            for name, info in data.get("node_types", {}).items()
        }
        edge_labels = {
            label: EdgeLabel(label=label, version=str(info.get("version", "0.0.0")))
            for label, info in data.get("edge_labels", {}).items()
        }
        version = str(data.get("version", "0.0.0"))
        return GraphSchema(
            version=version, node_types=node_types, edge_labels=edge_labels
        )

    @classmethod
    def load_default(cls) -> "GraphSchema":
        """Load the built-in schema packaged with ume."""
        schema_path = resources.files("ume.schemas").joinpath("graph_schema.yaml")
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


def load_default_schema() -> GraphSchema:
    """Helper to load the default graph schema."""
    return GraphSchema.load_default()


# Load schema on module import for convenience, but allow optional dependency
try:
    DEFAULT_SCHEMA = load_default_schema()
except Exception:  # pragma: no cover - optional dependency missing
    DEFAULT_SCHEMA = None  # type: ignore
