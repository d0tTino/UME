# src/ume/snapshot.py
import json
from typing import Union, TYPE_CHECKING, Dict, Any # Added Dict, Any
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

    The snapshot will include the data returned by graph.dump(), which
    currently consists of nodes. The JSON file is pretty-printed with an
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
    snapshot_graph_to_file, with a top-level "nodes" key.

    Args:
        path: The file path (string or pathlib.Path object) from which
              to load the JSON snapshot.

    Returns:
        A new MockGraph instance populated with data from the snapshot file.

    Raises:
        FileNotFoundError: If the specified path does not exist.
        json.JSONDecodeError: If the file content is not valid JSON.
        SnapshotError: If the JSON data does not conform to the expected
                       structure (e.g., missing "nodes" key, "nodes" is not
                       a dictionary, or individual node attributes are not
                       dictionaries).
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

    return graph
```
