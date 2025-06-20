# src/ume/snapshot.py
import json
from typing import Union, List, Tuple, Any
import pathlib  # For type hinting path-like objects

from .persistent_graph import PersistentGraph
from .graph_adapter import IGraphAdapter
from .processing import ProcessingError


def _no_duplicate_pairs_hook(pairs: List[Tuple[str, Any]]) -> dict:
    """Object pairs hook for ``json.load`` that rejects duplicate keys."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SnapshotError(f"Duplicate key '{key}' encountered in snapshot.")
        result[key] = value
    return result


class SnapshotError(ValueError):
    """Custom exception for snapshot loading or validation errors."""

    pass


def snapshot_graph_to_file(
    graph: IGraphAdapter, path: Union[str, pathlib.Path]
) -> None:
    """
    Snapshots the given graph's current state to a JSON file.

    The snapshot includes the data returned by ``graph.dump()``, which
    contains both nodes and edges. The JSON file is pretty-printed with an
    indent of 2 spaces.

    Args:
        graph: The graph instance to snapshot.
        path: The file path (string or pathlib.Path object) where the
              JSON snapshot will be saved.

    Raises:
        IOError: If an error occurs during file writing.
        TypeError: If the data from graph.dump() is not JSON serializable.
    """
    dumped_data = graph.dump()  # {"nodes": ..., "edges": ...}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dumped_data, f, indent=2)


def load_graph_from_file(path: Union[str, pathlib.Path]) -> PersistentGraph:
    """
    Loads a graph state from a JSON snapshot file into a new PersistentGraph instance.

    The JSON file is expected to contain data previously saved by
    `snapshot_graph_to_file`. It should have a top-level "nodes" key mapping
    to a dictionary of nodes and their attributes. Optionally, it can also
    contain an "edges" key mapping to a list of edge tuples
    (source_node_id, target_node_id, label).

    Args:
        path (Union[str, pathlib.Path]): The file path from which to load
              the JSON snapshot.

    Returns:
        PersistentGraph: A new PersistentGraph instance populated with data from the snapshot file.

    Raises:
        FileNotFoundError: If the specified path does not exist.
        json.JSONDecodeError: If the file content is not valid JSON.
        SnapshotError: If the JSON data does not conform to the expected
                       structure (e.g., missing "nodes" key, "nodes" or "edges"
                       have incorrect types, or individual node/edge items are
                       malformed).
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f, object_pairs_hook=_no_duplicate_pairs_hook)
    except FileNotFoundError:
        raise FileNotFoundError(f"Snapshot file not found at path: {path}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Error decoding JSON from snapshot file {path}: {e.msg}", e.doc, e.pos
        )

    if not isinstance(data, dict):
        raise SnapshotError(
            f"Invalid snapshot format: root should be a dictionary, got {type(data).__name__}."
        )

    if "nodes" not in data:
        raise SnapshotError(
            "Invalid snapshot format: missing 'nodes' key at the root level."
        )

    if not isinstance(data["nodes"], dict):
        raise SnapshotError(
            f"Invalid snapshot format: 'nodes' should be a dictionary, got {type(data['nodes']).__name__}."
        )

    graph = PersistentGraph(":memory:")
    seen_node_ids = set()
    for node_id, attributes in data["nodes"].items():
        if node_id in seen_node_ids:
            raise SnapshotError(f"Duplicate node ID '{node_id}' encountered in snapshot.")
        if not isinstance(attributes, dict):
            raise SnapshotError(
                f"Invalid snapshot format for node '{node_id}': attributes should be a dictionary, "
                f"got {type(attributes).__name__}."
            )
        seen_node_ids.add(node_id)
        # Since MockGraph.add_node expects attributes to be Dict[str, Any],
        # and json.load ensures keys are strings, this should be fine.
        graph.add_node(node_id, attributes.copy())  # Use .copy() for attributes

    # Load edges if present
    if "edges" in data:
        if not isinstance(data["edges"], list):
            raise SnapshotError(
                f"Invalid snapshot format: 'edges' should be a list, got {type(data['edges']).__name__}."
            )

        loaded_edges: List[Tuple[str, str, str]] = []
        seen_edges = set()
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
            edge_tuple = tuple(edge_data)
            if edge_tuple in seen_edges:
                raise SnapshotError(
                    f"Duplicate edge {edge_tuple} encountered in snapshot."
                )
            seen_edges.add(edge_tuple)
            loaded_edges.append(edge_tuple)

        # Use public API to add edges for consistency
        for src, tgt, lbl in loaded_edges:
            try:
                graph.add_edge(src, tgt, lbl)
            except ProcessingError as e:
                raise SnapshotError(
                    f"Error adding edge ({src}, {tgt}, {lbl}): {e}"
                ) from e

    return graph


def load_graph_into_existing(
    graph: IGraphAdapter, path: Union[str, pathlib.Path]
) -> None:
    """Load snapshot data from ``path`` into an existing graph adapter."""
    # Load into a temporary graph first so the target is untouched if parsing
    # fails. Only once loading completes without error do we replace the
    # contents of ``graph``.
    temp_graph = load_graph_from_file(path)

    graph.clear()
    for node_id in temp_graph.get_all_node_ids():
        attrs = temp_graph.get_node(node_id) or {}
        graph.add_node(node_id, attrs)
    for src, tgt, lbl in temp_graph.get_all_edges():
        graph.add_edge(src, tgt, lbl)
