# src/ume/graph_adapter.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

# To avoid circular dependency if ProcessingError is defined in processing.py
# and processing.py imports IGraphAdapter.
# We can define a base GraphError here or have adapter methods specify
# that they can raise a generic Exception or a specific error type
# that implementations must adhere to.
# For now, let's assume a generic Exception in docstring, but implementations
# like MockGraph will use ProcessingError from ume.processing.
# Alternatively, we could forward declare ProcessingError if it's complex.
# Let's try importing it under TYPE_CHECKING for now.

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .processing import ProcessingError # Used in docstrings, implementations will raise it

class IGraphAdapter(ABC):
    """
    Abstract Base Class defining the interface for graph operations,
    including node and edge manipulation, and graph state retrieval.

    This interface allows different graph backend implementations (e.g.,
    in-memory mock, database-backed) to be used interchangeably by
    the event processing logic.
    """

    @abstractmethod
    def add_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        """
        Adds a new node to the graph.

        Args:
            node_id: The unique identifier for the node.
            attributes: A dictionary of attributes for the node.

        Raises:
            ProcessingError (or similar): If the node_id already exists.
        """
        pass

    @abstractmethod
    def update_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        """
        Updates attributes of an existing node.

        Args:
            node_id: The unique identifier for the node to update.
            attributes: A dictionary of attributes to update.
                        Existing attributes will be updated; new attributes
                        will be added.

        Raises:
            ProcessingError (or similar): If the node_id does not exist.
        """
        pass

    @abstractmethod
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a node and its attributes from the graph.

        Args:
            node_id: The unique identifier for the node.

        Returns:
            A dictionary of the node's attributes if the node exists,
            otherwise None.
        """
        pass

    @abstractmethod
    def node_exists(self, node_id: str) -> bool:
        """
        Checks if a node exists in the graph.

        Args:
            node_id: The unique identifier for the node.

        Returns:
            True if the node exists, False otherwise.
        """
        pass

    @abstractmethod
    def dump(self) -> Dict[str, Any]:
        """
        Returns a dictionary representation of the graph's current state.

        This is primarily for serialization or debugging. The exact structure
        (e.g., inclusion of nodes, edges) may depend on the implementation.
        For consistency, it's recommended to return a dict with keys like
        "nodes" and "edges".

        Returns:
            A dictionary representing the graph state.
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """
        Removes all nodes and edges from the graph, resetting it to an empty state.
        """
        pass

    @abstractmethod
    def get_all_node_ids(self) -> list[str]:
        """
        Retrieves a list of all node identifiers currently in the graph.

        Returns:
            A list of strings, where each string is a unique node ID.
            Returns an empty list if the graph contains no nodes.
        """
        pass

    @abstractmethod
    def find_connected_nodes(self, node_id: str, edge_label: Optional[str] = None) -> list[str]:
        """
        Finds nodes connected to a given node, optionally via a specific edge label.

        This method is a placeholder for basic connectivity queries. Implementations
        may vary based on their support for edges and edge labels.

        Args:
            node_id: The identifier of the starting node.
            edge_label: (Optional) If provided, filter connections by this edge label.
                        If None, consider all connections.

        Returns:
            A list of node IDs connected to the given node.
            Returns an empty list if no connected nodes are found or if the
            starting node does not exist or if edges are not supported.

        Raises:
            ProcessingError (or similar): If the specified node_id does not exist in the graph
                                        (implementations may choose this behavior).
        """
        pass

    @abstractmethod
    def add_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        """
        Adds a directed, labeled edge between two existing nodes.

        Args:
            source_node_id: The identifier of the source node (origin of the edge).
            target_node_id: The identifier of the target node (destination of the edge).
            label: A string label describing the type of relationship or connection.

        Raises:
            ProcessingError (or similar): If either the source_node_id or
                                        target_node_id does not exist in the graph.
                                        Implementations may also raise errors for
                                        invalid labels or other constraints.
        """
        pass

    @abstractmethod
    def get_all_edges(self) -> list[tuple[str, str, str]]:
        """
        Retrieves a list of all edges currently in the graph.

        Each edge is represented as a tuple: (source_node_id, target_node_id, label).

        Returns:
            A list of tuples, where each tuple represents an edge.
            Returns an empty list if the graph contains no edges.
        """
        pass
```
