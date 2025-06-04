# src/ume/snapshot.py
import json
from typing import Union, TYPE_CHECKING, List, Tuple
import pathlib # For type hinting path-like objects

# Ensure MockGraph is available for instantiation and type hinting
from .graph import MockGraph

# TYPE_CHECKING block for MockGraph might be redundant if imported directly above,
# but doesn't harm. It's good practice if snapshot.py were imported by graph.py.
if TYPE_CHECKING:
    pass # MockGraph already imported

class SnapshotError(ValueError):
    """Custom exception for snapshot loading or validation errors."""
    pass

def snapshot_graph_to_file(graph: MockGraph, path: Union[str, pathlib.Path]) -> None:
    """
    Snapshots the given MockGraph's current state to a JSON file.

    The snapshot includes the data returned by ``graph.dump()``, which
    contains both nodes and edges. The JSON file is pretty-printed with an
    indent of 2 spaces.

    Args:
        graph: The MockGraph instance to snapshot.
        path: The file path (string or pathlib.Path object) where the
              JSON snapshot will be saved.

    Raises:
        IOError: If an error occurs during file writing.
        TypeError: If the data from graph.dump() is not JSON serializable.
    """
    dumped_data = graph.dump() # This currently returns {"nodes": ...}
    with open(path, "w", encoding='utf-8') as f:
        json.dump(dumped_data, f, indent=2)

def load_graph_from_file(path: Union[str, pathlib.Path]) -> MockGraph:
    """
    Loads a graph state from a JSON snapshot file into a new MockGraph instance.

    The JSON file is expected to contain data previously saved by
    `snapshot_graph_to_file`. It should have a top-level "nodes" key mapping
    to a dictionary of nodes and their attributes. Optionally, it can also
    contain an "edges" key mapping to a list of edge tuples
    (source_node_id, target_node_id, label).

    Args:
        path (Union[str, pathlib.Path]): The file path from which to load
              the JSON snapshot.

    Returns:
        MockGraph: A new MockGraph instance populated with data from the snapshot file.

    Raises:
        FileNotFoundError: If the specified path does not exist.
        json.JSONDecodeError: If the file content is not valid JSON.
        SnapshotError: If the JSON data does not conform to the expected
                       structure (e.g., missing "nodes" key, "nodes" or "edges"
                       have incorrect types, or individual node/edge items are
                       malformed).
    """
    try:
        with open(path, "r", encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Snapshot file not found at path: {path}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Error decoding JSON from snapshot file {path}: {e.msg}", e.doc, e.pos)

    if not isinstance(data, dict):
        raise SnapshotError(f"Invalid snapshot format: root should be a dictionary, got {type(data).__name__}.")

    if "nodes" not in data:
        raise SnapshotError("Invalid snapshot format: missing 'nodes' key at the root level.")

    if not isinstance(data["nodes"], dict):
        raise SnapshotError(f"Invalid snapshot format: 'nodes' should be a dictionary, got {type(data['nodes']).__name__}.")

    graph = MockGraph()
    for node_id, attributes in data["nodes"].items():
        if not isinstance(attributes, dict):
            raise SnapshotError(
                f"Invalid snapshot format for node '{node_id}': attributes should be a dictionary, "
                f"got {type(attributes).__name__}."
            )
        # Since MockGraph.add_node expects attributes to be Dict[str, Any],
        # and json.load ensures keys are strings, this should be fine.
        graph.add_node(node_id, attributes.copy()) # Use .copy() for attributes

    # Load edges if present
    if "edges" in data:
        if not isinstance(data["edges"], list):
            raise SnapshotError(
                f"Invalid snapshot format: 'edges' should be a list, got {type(data['edges']).__name__}."
            )

        loaded_edges: List[Tuple[str, str, str]] = []
        for i, edge_data in enumerate(data["edges"]):
            if not isinstance(edge_data, (list, tuple)):
                raise SnapshotError(
                    f"Invalid snapshot format for edge at index {i}: each edge should be a list or tuple, "
                    f"got {type(edge_data).__name__}."
                )
            if len(edge_data) != 3:
                raise SnapshotError(
                    f"Invalid snapshot format for edge at index {i}: each edge must have 3 elements "
                    f"(source, target, label), got {len(edge_data)} elements."
                )
            if not all(isinstance(item, str) for item in edge_data):
                raise SnapshotError(
                    f"Invalid snapshot format for edge at index {i}: all edge elements "
                    f"(source, target, label) must be strings."
                )
            loaded_edges.append(tuple(edge_data))

        # Use public API to add edges for consistency
        for src, tgt, lbl in loaded_edges:
            graph.add_edge(src, tgt, lbl)

    return graph
