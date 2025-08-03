# src/ume/graph.py
from typing import Any, DefaultDict, Dict, List, Optional, Tuple

from .graph_adapter import IGraphAdapter
from .graph_algorithms import GraphAlgorithmsMixin
from .graph_schema import DEFAULT_SCHEMA
from .processing import ProcessingError


class MockGraph(GraphAlgorithmsMixin, IGraphAdapter):
    """
    A simple mock graph representation implementing IGraphAdapter, for testing.

    This class simulates a graph by storing nodes and their attributes
    in an in-memory dictionary, and edges as a list of tuples.
    It is not intended for production use but rather to facilitate testing
    of graph update logic without requiring a full graph database.
    It implements the IGraphAdapter interface, including basic edge support.
    """

    def __init__(self) -> None:
        """Initializes an empty graph with no nodes or edges."""
        self._nodes: Dict[str, Dict[str, Any]] = {}
        # Track nodes/edges that have been redacted
        self._redacted_nodes: set[str] = set()
        self._redacted_edges: set[Tuple[str, str, str]] = set()
        # Store edges in an adjacency list for faster lookups:
        #   source_id -> [(target_id, label, permission_level), ...]
        self._edges: DefaultDict[str, List[Tuple[str, str, Optional[str]]]] = DefaultDict(list)

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
        if node_id in self._redacted_nodes:
            return None
        return self._nodes.get(node_id)

    def node_exists(self, node_id: str) -> bool:
        """
        Checks if a node exists in the graph.

        Args:
            node_id: The unique identifier for the node.

        Returns:
            True if the node exists, False otherwise.
        """
        return node_id in self._nodes and node_id not in self._redacted_nodes

    def get_all_node_ids(self) -> List[str]:
        """
        Retrieves a list of all node identifiers currently in the graph.

        Returns:
            A list of strings, where each string is a unique node ID.
            Returns an empty list if the graph contains no nodes.
        """
        return [nid for nid in self._nodes.keys() if nid not in self._redacted_nodes]

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

        edge_def = DEFAULT_SCHEMA.edge_labels.get(label)
        permission_level = edge_def.permission_level if edge_def else None
        self._edges[source_node_id].append((target_node_id, label, permission_level))

    def get_all_edges(self) -> List[Tuple[str, str, str, Optional[str]]]:  # type: ignore[override]
        """
        Retrieves a list of all edges currently in the graph.

        Each edge is represented as a tuple:
            (source_node_id, target_node_id, label, permission_level).

        Returns:
            A list of tuples, where each tuple represents an edge.
            Returns an empty list if the graph contains no edges.
        """
        all_edges: List[Tuple[str, str, str, Optional[str]]] = []
        for src, targets in self._edges.items():
            for tgt, lbl, perm in targets:
                if (
                    src not in self._redacted_nodes
                    and tgt not in self._redacted_nodes
                    and (src, tgt, lbl) not in self._redacted_edges
                ):
                    all_edges.append((src, tgt, lbl, perm))
        return all_edges

    def delete_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        """
        Removes a specific directed, labeled edge from the graph.

        Args:
            source_node_id: The identifier of the source node of the edge.
            target_node_id: The identifier of the target node of the edge.
            label: The label of the edge to remove.

        Raises:
            ProcessingError: If the specified edge (source, target, label)
                             does not exist in the graph or if either node
                             does not exist.
        """
        if not self.node_exists(source_node_id) or not self.node_exists(target_node_id):
            raise ProcessingError(
                f"Cannot delete edge because node '{source_node_id}' or '{target_node_id}' does not exist."
            )

        edges_from_source = self._edges.get(source_node_id)
        if not edges_from_source:
            raise ProcessingError(
                f"Edge {(source_node_id, target_node_id, label)} does not exist and cannot be deleted."
            )

        index_to_remove: Optional[int] = None
        for idx, (tgt, lbl, _perm) in enumerate(edges_from_source):
            if tgt == target_node_id and lbl == label:
                index_to_remove = idx
                break
        if index_to_remove is None:
            raise ProcessingError(
                f"Edge {(source_node_id, target_node_id, label)} does not exist and cannot be deleted."
            )
        edges_from_source.pop(index_to_remove)
        if not edges_from_source:
            del self._edges[source_node_id]
        self._redacted_edges.discard((source_node_id, target_node_id, label))

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

        connected_nodes: List[str] = []
        for target, lbl, _perm in self._edges.get(node_id, []):
            if (edge_label is None or lbl == edge_label) and (
                node_id not in self._redacted_nodes
                and target not in self._redacted_nodes
                and (node_id, target, lbl) not in self._redacted_edges
            ):
                connected_nodes.append(target)
        return connected_nodes

    def get_nodes_by_user(self, user_id: str) -> List[str]:
        """Return node IDs owned by the specified user."""
        owned_nodes: List[str] = []
        for src, targets in self._edges.items():
            if src in self._redacted_nodes:
                continue
            for tgt, lbl, _perm in targets:
                if (
                    lbl == "OWNED_BY"
                    and tgt == user_id
                    and tgt not in self._redacted_nodes
                    and (src, tgt, lbl) not in self._redacted_edges
                ):
                    owned_nodes.append(src)
        return owned_nodes

    def get_nodes_shared_with(self, group_id: str) -> List[str]:
        """Return node IDs shared with the specified group."""
        shared_nodes: List[str] = []
        for src, targets in self._edges.items():
            if src in self._redacted_nodes:
                continue
            for tgt, lbl, _perm in targets:
                if (
                    lbl == "SHARED_WITH"
                    and tgt == group_id
                    and tgt not in self._redacted_nodes
                    and (src, tgt, lbl) not in self._redacted_edges
                ):
                    shared_nodes.append(src)
        return shared_nodes

    def clear(self) -> None:
        """Removes all nodes and edges from the graph."""
        self._nodes.clear()
        self._edges.clear()
        self._redacted_nodes.clear()
        self._redacted_edges.clear()

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
            (source_node_id, target_node_id, label, permission_level).
        """
        edge_list: List[Tuple[str, str, str, Optional[str]]] = []
        for src, targets in self._edges.items():
            for tgt, lbl, perm in targets:
                if (
                    src not in self._redacted_nodes
                    and tgt not in self._redacted_nodes
                    and (src, tgt, lbl) not in self._redacted_edges
                ):
                    edge_list.append((src, tgt, lbl, perm))
        return {
            "nodes": {
                nid: attrs.copy()
                for nid, attrs in self._nodes.items()
                if nid not in self._redacted_nodes
            },
            "edges": edge_list,
        }

    def redact_node(self, node_id: str) -> None:
        if node_id not in self._nodes:
            raise ProcessingError(f"Node '{node_id}' not found to redact.")
        self._redacted_nodes.add(node_id)

    def redact_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        edges_from_source = self._edges.get(source_node_id)
        if not edges_from_source:
            raise ProcessingError(
                f"Edge {(source_node_id, target_node_id, label)} does not exist and cannot be redacted."
            )
        for tgt, lbl, _perm in edges_from_source:
            if tgt == target_node_id and lbl == label:
                self._redacted_edges.add((source_node_id, target_node_id, label))
                return
        raise ProcessingError(
            f"Edge {(source_node_id, target_node_id, label)} does not exist and cannot be redacted."
        )

    def close(self) -> None:
        """Mock adapter does not hold resources."""
        pass
