# src/ume/graph.py
from typing import Dict, Any, Optional, List, Tuple, DefaultDict
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
        # Track nodes/edges that have been redacted
        self._redacted_nodes: set[str] = set()
        self._redacted_edges: set[Tuple[str, str, str]] = set()
        # Store edges in an adjacency list for faster lookups: source_id -> [(target_id, label), ...]
        self._edges: DefaultDict[str, List[Tuple[str, str]]] = DefaultDict(list)

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
        self._edges[source_node_id].append((target_node_id, label))

    def get_all_edges(self) -> List[Tuple[str, str, str]]:
        """
        Retrieves a list of all edges currently in the graph.

        Each edge is represented as a tuple: (source_node_id, target_node_id, label).

        Returns:
            A list of tuples, where each tuple represents an edge.
            Returns an empty list if the graph contains no edges.
        """
        all_edges: List[Tuple[str, str, str]] = []
        for src, targets in self._edges.items():
            for tgt, lbl in targets:
                if (
                    src not in self._redacted_nodes
                    and tgt not in self._redacted_nodes
                    and (src, tgt, lbl) not in self._redacted_edges
                ):
                    all_edges.append((src, tgt, lbl))
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
                             does not exist in the graph.
                             (Note: This implementation does not currently check
                             if source/target nodes themselves exist prior to attempting
                             edge removal, relying on the edge's existence.)
        """
        edge_to_remove = (target_node_id, label)
        edges_from_source = self._edges.get(source_node_id)
        if not edges_from_source or edge_to_remove not in edges_from_source:
            raise ProcessingError(
                f"Edge {(source_node_id, target_node_id, label)} does not exist and cannot be deleted."
            )
        edges_from_source.remove(edge_to_remove)
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
        for target, lbl in self._edges.get(node_id, []):
            if (edge_label is None or lbl == edge_label) and (
                node_id not in self._redacted_nodes
                and target not in self._redacted_nodes
                and (node_id, target, lbl) not in self._redacted_edges
            ):
                connected_nodes.append(target)
        return connected_nodes

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
            (source_node_id, target_node_id, label).
        """
        edge_list: List[Tuple[str, str, str]] = []
        for src, targets in self._edges.items():
            for tgt, lbl in targets:
                if (
                    src not in self._redacted_nodes
                    and tgt not in self._redacted_nodes
                    and (src, tgt, lbl) not in self._redacted_edges
                ):
                    edge_list.append((src, tgt, lbl))
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
        edge_tuple = (target_node_id, label)
        if edge_tuple not in self._edges.get(source_node_id, []):
            raise ProcessingError(
                f"Edge {(source_node_id, target_node_id, label)} does not exist and cannot be redacted."
            )
        self._redacted_edges.add((source_node_id, target_node_id, label))

    def close(self) -> None:
        """Mock adapter does not hold resources."""
        pass

    # ---- Traversal and pathfinding ---------------------------------

    def shortest_path(self, source_id: str, target_id: str) -> List[str]:
        if not self.node_exists(source_id) or not self.node_exists(target_id):
            return []
        visited = {source_id: None}
        queue: List[str] = [source_id]
        while queue:
            current = queue.pop(0)
            if current == target_id:
                break
            for neighbor in self.find_connected_nodes(current):
                if neighbor not in visited:
                    visited[neighbor] = current
                    queue.append(neighbor)
        if target_id not in visited:
            return []
        path = [target_id]
        while visited[path[-1]] is not None:
            prev = visited[path[-1]]
            assert prev is not None
            path.append(prev)
        path.reverse()
        return path

    def traverse(
        self,
        start_node_id: str,
        depth: int,
        edge_label: Optional[str] = None,
    ) -> List[str]:
        if not self.node_exists(start_node_id):
            raise ProcessingError(f"Node '{start_node_id}' not found.")
        visited: set[str] = {start_node_id}
        queue: List[tuple[str, int]] = [(start_node_id, 0)]
        result: List[str] = []
        while queue:
            node, d = queue.pop(0)
            if d >= depth:
                continue
            for neighbor in self.find_connected_nodes(node, edge_label):
                if neighbor not in visited:
                    visited.add(neighbor)
                    result.append(neighbor)
                    queue.append((neighbor, d + 1))
        return result

    def extract_subgraph(
        self,
        start_node_id: str,
        depth: int,
        edge_label: Optional[str] = None,
        since_timestamp: Optional[int] = None,
    ) -> Dict[str, Any]:
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Tuple[str, str, str]] = []
        to_visit = [(start_node_id, 0)]
        visited: set[str] = set()
        while to_visit:
            node, d = to_visit.pop(0)
            if node in visited or d > depth:
                continue
            visited.add(node)
            data = self.get_node(node) or {}
            include = True
            if since_timestamp is not None:
                ts = data.get("timestamp")
                if ts is None or int(ts) < since_timestamp:
                    include = False
            if include:
                nodes[node] = data.copy()
            if d == depth:
                continue
            for tgt, lbl in self._edges.get(node, []):
                if lbl == edge_label or edge_label is None:
                    if (
                        node not in self._redacted_nodes
                        and tgt not in self._redacted_nodes
                        and (node, tgt, lbl) not in self._redacted_edges
                    ):
                        edges.append((node, tgt, lbl))
                        to_visit.append((tgt, d + 1))
        return {"nodes": nodes, "edges": edges}
