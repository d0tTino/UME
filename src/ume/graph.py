# src/ume/graph.py
from typing import Dict, Any, Optional, List, Tuple  # Added List, Tuple
from .graph_adapter import IGraphAdapter
from .processing import ProcessingError


class MockGraph(IGraphAdapter):
    """
    A simple mock graph representation implementing IGraphAdapter, for testing.

    This class simulates a graph by storing nodes and their attributes
    in an in-memory dictionary, and edges as a list of tuples.
    It is not intended for production use but rather to facilitate testing
    of graph update logic without requiring a full graph database.
    It implements the IGraphAdapter interface, including basic edge support.
    """

    def __init__(self):
        """Initializes an empty graph with no nodes or edges."""
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._edges: List[Tuple[str, str, str]] = []  # (source_id, target_id, label)

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
        self._nodes[node_id] = attributes

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

    def get_all_node_ids(self) -> List[str]:
        """
        Retrieves a list of all node identifiers currently in the graph.

        Returns:
            A list of strings, where each string is a unique node ID.
            Returns an empty list if the graph contains no nodes.
        """
        return list(self._nodes.keys())

    def add_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        """
        Adds a directed, labeled edge between two existing nodes.

        Args:
            source_node_id: The identifier of the source node (origin of the edge).
            target_node_id: The identifier of the target node (destination of the edge).
            label: A string label describing the type of relationship or connection.

        Raises:
            ProcessingError: If either the source_node_id or target_node_id
                             does not exist in the graph.
        """
        if not self.node_exists(source_node_id) or not self.node_exists(target_node_id):
            raise ProcessingError(
                f"Both source node '{source_node_id}' and target node '{target_node_id}' "
                "must exist to add an edge."
            )
        self._edges.append((source_node_id, target_node_id, label))

    def add_edges_bulk(self, edges: list[tuple[str, str, str]]) -> None:
        """Add multiple edges sequentially using :meth:`add_edge`."""
        for source, target, label in edges:
            self.add_edge(source, target, label)

    def get_all_edges(self) -> List[Tuple[str, str, str]]:
        """
        Retrieves a list of all edges currently in the graph.

        Each edge is represented as a tuple: (source_node_id, target_node_id, label).

        Returns:
            A list of tuples, where each tuple represents an edge.
            Returns an empty list if the graph contains no edges.
        """
        return list(self._edges)  # Return a copy

    def delete_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        """
        Removes a specific directed, labeled edge from the graph.

        Args:
            source_node_id: The identifier of the source node of the edge.
            target_node_id: The identifier of the target node of the edge.
            label: The label of the edge to remove.

        Raises:
            ProcessingError: If the specified edge (source, target, label)
                             does not exist in the graph.
                             (Note: This implementation does not currently check
                             if source/target nodes themselves exist prior to attempting
                             edge removal, relying on the edge's existence.)
        """
        edge_to_remove = (source_node_id, target_node_id, label)
        try:
            self._edges.remove(edge_to_remove)
        except ValueError:  # .remove() raises ValueError if item not found
            raise ProcessingError(
                f"Edge {edge_to_remove} does not exist and cannot be deleted."
            )

    def find_connected_nodes(
        self, node_id: str, edge_label: Optional[str] = None
    ) -> List[str]:
        """
        Finds nodes connected to a given node, optionally via a specific edge label.

        This implementation iterates through the stored edges.

        Args:
            node_id: The identifier of the starting node.
            edge_label: (Optional) If provided, filter connections by this edge label.
                        If None, consider all connections from the source node.

        Returns:
            A list of target node IDs connected from the given source node,
            matching the optional edge_label. Returns an empty list if no
            such connections are found.

        Raises:
            ProcessingError: If the specified source_node_id does not exist in the graph.
        """
        if not self.node_exists(node_id):
            raise ProcessingError(f"Node '{node_id}' not found.")

        connected_nodes = []
        for src, target, lbl in self._edges:
            if src == node_id:
                if edge_label is None or lbl == edge_label:
                    connected_nodes.append(target)
        return connected_nodes

    def clear(self) -> None:
        """Removes all nodes and edges from the graph."""
        self._nodes.clear()
        self._edges.clear()

    @property
    def node_count(self) -> int:
        """Returns the number of nodes in the graph."""
        return len(self._nodes)

    def dump(self) -> Dict[str, Any]:
        """
        Returns a dictionary representation of the graph's current state,
        including both nodes and edges.

        The primary use case is for serialization (e.g., to JSON) or debugging.

        Returns:
            A dictionary with "nodes" and "edges" keys.
            "nodes" maps to a dictionary of all nodes and their attributes.
            "edges" maps to a list of all edges, where each edge is a tuple
            (source_node_id, target_node_id, label).
        """
        node_copies = {k: v.copy() for k, v in self._nodes.items()}
        return {"nodes": node_copies, "edges": list(self._edges)}
