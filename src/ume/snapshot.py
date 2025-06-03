# src/ume/snapshot.py
import json
import os # For os.path.exists if needed, though Path.exists() is preferred
from typing import Union, TYPE_CHECKING, Dict, Any, List, Tuple 
import pathlib

# Ensure MockGraph is available for instantiation and type hinting
from .graph import MockGraph
from .processing import ProcessingError # For catching errors from graph.add_node

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
    Ensures parent directories for the specified path are created.

    Args:
        graph (MockGraph): The MockGraph instance to snapshot.
        path (Union[str, pathlib.Path]): The file path where the JSON snapshot will be saved.

    Raises:
        SnapshotError: If writing the snapshot fails due to I/O issues,
                       JSON processing errors, or other unexpected errors.
    """
    path_obj = pathlib.Path(path)
    try:
        # Ensure the parent directory exists
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        dumped_data = graph.dump() # This currently returns {"nodes": ..., "edges": ...}
        
        with open(path_obj, "w", encoding='utf-8') as f:
            json.dump(dumped_data, f, indent=2)
    except (IOError, OSError, TypeError) as e: # More specific common errors for file I/O and JSON
        raise SnapshotError(f"Failed to write snapshot to {path_obj}: {e}")
    except Exception as e: # Catch any other unexpected error
        raise SnapshotError(f"An unexpected error occurred while writing snapshot to {path_obj}: {e}")


def load_graph_from_file(path: Union[str, pathlib.Path]) -> MockGraph:
    """
    Loads a graph state from a JSON snapshot file into a new MockGraph instance.

    The JSON file is expected to contain data previously saved by
    `snapshot_graph_to_file`. It should have a top-level "nodes" key mapping
    to a dictionary of nodes and their attributes, and optionally an "edges"
    key mapping to a list of edge tuples (source_node_id, target_node_id, label).
    Node and edge data undergoes validation.

    Args:
        path (Union[str, pathlib.Path]): The file path from which to load
              the JSON snapshot.

    Returns:
        MockGraph: A new MockGraph instance populated with data from the snapshot file.

    Raises:
        SnapshotError: If the snapshot file is not found, cannot be read,
                       contains invalid JSON, does not conform to the expected
                       structure (e.g., missing "nodes" key, "nodes" or "edges"
                       have incorrect types, individual node/edge items are
                       malformed, or an edge references a non-existent node
                       within the snapshot). Also raised if there's an error
                       adding a node to the graph (e.g., duplicate node ID in snapshot).
    """
    path_obj = pathlib.Path(path)
    if not path_obj.exists():
        raise SnapshotError(f"Snapshot file not found: {path_obj}")

    try:
        with open(path_obj, "r", encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise SnapshotError(f"Failed to parse JSON from snapshot file {path_obj}: {e}")
    except (IOError, OSError) as e:
        raise SnapshotError(f"Failed to read snapshot file {path_obj}: {e}")
    except Exception as e: # Catch any other unexpected error during file read/parse
        raise SnapshotError(f"An unexpected error occurred while reading/parsing snapshot {path_obj}: {e}")

    if not isinstance(data, dict):
        raise SnapshotError(f"Invalid snapshot format: root should be a dictionary, got {type(data).__name__}.")
    
    if "nodes" not in data:
        raise SnapshotError("Invalid snapshot format: missing 'nodes' key at the root level.")

    if not isinstance(data["nodes"], dict):
        raise SnapshotError(f"Invalid snapshot format: 'nodes' should be a dictionary, got {type(data['nodes']).__name__}.")

    graph = MockGraph()
    # Load nodes first
    for node_id, attributes in data["nodes"].items():
        if not isinstance(node_id, str): # Ensure node_id from JSON key is string (json.load should do this)
            raise SnapshotError(f"Invalid snapshot format: node ID must be a string, got {type(node_id).__name__} for '{node_id}'.")
        if not isinstance(attributes, dict):
            raise SnapshotError(
                f"Invalid snapshot format for node '{node_id}': attributes should be a dictionary, "
                f"got {type(attributes).__name__}."
            )
        try:
            graph.add_node(node_id, attributes.copy()) # Use .copy() for attributes
        except ProcessingError as pe: # Catch errors like duplicate node ID from MockGraph.add_node
            raise SnapshotError(f"Error adding node '{node_id}' from snapshot: {pe}")
    
    # Load edges if present
    if "edges" in data:
        if not isinstance(data["edges"], list):
            raise SnapshotError(
                f"Invalid snapshot format: 'edges' should be a list, got {type(data['edges']).__name__}."
            )
        
        loaded_edges_tuples: List[Tuple[str, str, str]] = []
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
            
            # Check if source and target nodes for the edge exist in the loaded nodes
            src, tgt, _ = tuple(edge_data)
            if src not in graph._nodes or tgt not in graph._nodes: # Check against already loaded nodes in *this* graph
                 raise SnapshotError(f"Invalid edge found {tuple(edge_data)} at index {i}: source or target node not loaded from snapshot's nodes list.")
            loaded_edges_tuples.append(tuple(edge_data))
        
        graph._edges = loaded_edges_tuples # Direct assignment after all validations pass

    return graph
```
