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
    Abstract Base Class defining the interface for graph operations.

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
```
