# src/ume/graph.py
from typing import Dict, Any, Optional
from .graph_adapter import IGraphAdapter
from .processing import ProcessingError

class MockGraph(IGraphAdapter):
    """
    A simple mock graph representation implementing IGraphAdapter, for testing.

    This class simulates a graph by storing nodes and their attributes
    in an in-memory dictionary. It is not intended for production use
    but rather to facilitate testing of graph update logic without
    requiring a full graph database. It implements the IGraphAdapter interface.
    """

    def __init__(self):
        """Initializes an empty graph."""
        self._nodes: Dict[str, Dict[str, Any]] = {}
        # In a real graph, you might also have self._edges or similar

    def add_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        """
        Adds a new node to the graph. Conforms to IGraphAdapter.

        Args:
            node_id: The unique identifier for the node.
            attributes: A dictionary of attributes for the node. An empty dictionary
                        can be provided if the node has no initial attributes.

        Raises:
            ProcessingError: If the node_id already exists.
        """
        if node_id in self._nodes:
            raise ProcessingError(f"Node '{node_id}' already exists.")
        self._nodes[node_id] = attributes # attributes is expected to be a dict per IGraphAdapter

    def update_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        """
        Updates attributes of an existing node. Conforms to IGraphAdapter.

        Args:
            node_id: The unique identifier for the node to update.
            attributes: A dictionary of attributes to update.
                        Existing attributes will be updated; new attributes
                        will be added. An empty dict for attributes will result
                        in no changes to existing attributes.

        Raises:
            ProcessingError: If the node_id does not exist.
        """
        if node_id not in self._nodes:
            raise ProcessingError(f"Node '{node_id}' not found for update.")
        self._nodes[node_id].update(attributes)

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

    def get_all_node_ids(self) -> list[str]:
        """
        Retrieves a list of all node identifiers currently in the graph.

        Returns:
            A list of strings, where each string is a unique node ID.
            Returns an empty list if the graph contains no nodes.
        """
        return list(self._nodes.keys())

    def find_connected_nodes(self, node_id: str, edge_label: Optional[str] = None) -> list[str]:
        """
        Finds nodes connected to a given node, optionally via a specific edge label.

        NOTE: MockGraph does not currently support explicit edge structures.
        This method will return an empty list if the starting node exists,
        and raise an error if the starting node does not exist.

        Args:
            node_id: The identifier of the starting node.
            edge_label: (Optional) If provided, filter connections by this edge label.
                        Currently ignored by MockGraph.

        Returns:
            An empty list, as MockGraph does not store edges.

        Raises:
            ProcessingError: If the specified node_id does not exist in the graph.
        """
        if not self.node_exists(node_id): # Or directly check self._nodes
            raise ProcessingError(f"Node '{node_id}' not found.")
        # MockGraph does not store edges, so always return an empty list for connected nodes.
        return []

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
