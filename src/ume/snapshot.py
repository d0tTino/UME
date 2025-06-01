# src/ume/snapshot.py
import json
from typing import Union, TYPE_CHECKING
import pathlib # For type hinting path-like objects

if TYPE_CHECKING:
    from .graph import MockGraph # For type hinting, avoid circular import if graph imports snapshot

def snapshot_graph_to_file(graph: 'MockGraph', path: Union[str, pathlib.Path]) -> None:
    """
    Snapshots the given MockGraph's current state to a JSON file.

    The snapshot will include the data returned by graph.dump(), which
    currently consists of nodes. The JSON file is pretty-printed with an
    indent of 2 spaces.

    Args:
        graph: The MockGraph instance to snapshot.
        path: The file path (string or pathlib.Path object) where the
              JSON snapshot will be saved.
    """
    dumped_data = graph.dump() # This currently returns {"nodes": ...}
    with open(path, "w", encoding='utf-8') as f:
        json.dump(dumped_data, f, indent=2)

```
