# src/ume/graph.py
from typing import Dict, Any, Optional

class MockGraph:
    """
    A simple mock graph representation for testing purposes.

    This class simulates a graph by storing nodes and their attributes
    in an in-memory dictionary. It is not intended for production use
    but rather to facilitate testing of graph update logic without
    requiring a full graph database.
    """

    def __init__(self):
        """Initializes an empty graph."""
        self._nodes: Dict[str, Dict[str, Any]] = {}
        # In a real graph, you might also have self._edges or similar

    def add_node(self, node_id: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """
        Adds a node to the graph or updates an existing node's attributes.

        If the node_id already exists, its attributes will be updated
        with the new attributes provided. If attributes is None,
        an empty attribute dictionary will be associated with the node.

        Args:
            node_id: The unique identifier for the node.
            attributes: A dictionary of attributes for the node.
        """
        if node_id in self._nodes and attributes:
            self._nodes[node_id].update(attributes)
        elif node_id not in self._nodes : # only add if attributes are not none, or node is new
             self._nodes[node_id] = attributes if attributes is not None else {}


    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a node and its attributes from the graph.

        Args:
            node_id: The unique identifier for the node.

        Returns:
            A dictionary of the node's attributes if the node exists,
            otherwise None.
        """
        return self._nodes.get(node_id)

    def node_exists(self, node_id: str) -> bool:
        """
        Checks if a node exists in the graph.

        Args:
            node_id: The unique identifier for the node.

        Returns:
            True if the node exists, False otherwise.
        """
        return node_id in self._nodes

    def clear(self) -> None:
        """Removes all nodes and edges from the graph."""
        self._nodes.clear()

    @property
    def node_count(self) -> int:
        """Returns the number of nodes in the graph."""
        return len(self._nodes)

    def dump(self) -> Dict[str, Any]:
        """
        Returns a dictionary representation of the graph's current state.

        The primary use case is for serialization (e.g., to JSON) or debugging.
        Currently, only nodes are included in the dump.

        Returns:
            A dictionary with a "nodes" key, where the value is a dictionary
            of all nodes and their attributes.
        """
        return {"nodes": self._nodes.copy()} # Return a copy to prevent external modification
