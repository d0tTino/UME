# src/ume/processing.py
from .event import Event
from .graph_adapter import IGraphAdapter # Use IGraphAdapter
# MockGraph import removed as it's no longer directly used for type hinting here

class ProcessingError(ValueError):
    """Custom exception for event processing errors."""
    pass

def apply_event_to_graph(event: Event, graph: IGraphAdapter) -> None:
    """
    Applies an event to a graph, modifying the graph based on event type and payload.

    This function uses the IGraphAdapter interface to interact with the graph,
    allowing for different graph backend implementations.

    Args:
        event: The Event object to apply.
        graph: An instance implementing the IGraphAdapter interface.

    Raises:
        ProcessingError: If the event payload is missing required fields
                         for the given event_type, or if the event_type is unknown.
    """
    if event.event_type == "CREATE_NODE":
        node_id = event.payload.get("node_id")
        if not node_id:
            raise ProcessingError(f"Missing 'node_id' in payload for CREATE_NODE event: {event.event_id}")
        if not isinstance(node_id, str):
            raise ProcessingError(f"'node_id' must be a string for CREATE_NODE event: {event.event_id}")

        attributes = event.payload.get("attributes", {}) # Default to empty dict if 'attributes' key is missing
        if not isinstance(attributes, dict): # Ensure attributes, if provided, is a dict
             raise ProcessingError(f"'attributes' must be a dictionary for CREATE_NODE event, if provided. Got: {type(attributes).__name__} for event: {event.event_id}")

        graph.add_node(node_id, attributes) # Call adapter's add_node

    elif event.event_type == "UPDATE_NODE_ATTRIBUTES":
        node_id = event.payload.get("node_id")
        if not node_id:
            raise ProcessingError(f"Missing 'node_id' in payload for UPDATE_NODE_ATTRIBUTES event: {event.event_id}")
        if not isinstance(node_id, str):
            raise ProcessingError(f"'node_id' must be a string for UPDATE_NODE_ATTRIBUTES event: {event.event_id}")

        if "attributes" not in event.payload:
            raise ProcessingError(f"Missing 'attributes' key in payload for UPDATE_NODE_ATTRIBUTES event: {event.event_id}")

        attributes = event.payload["attributes"]
        if not isinstance(attributes, dict):
            raise ProcessingError(f"'attributes' must be a dictionary for UPDATE_NODE_ATTRIBUTES event: {event.event_id}")
        if not attributes:
            raise ProcessingError(f"'attributes' dictionary cannot be empty for UPDATE_NODE_ATTRIBUTES event: {event.event_id}")

        graph.update_node(node_id, attributes) # Call adapter's update_node

    # Placeholder for other event types, e.g., DELETE_NODE, ADD_EDGE etc.
    # elif event.event_type == "DELETE_NODE":
    #     # Implementation for deleting a node
    #     pass

    else:
        # For now, we can choose to ignore unknown event types or raise an error.
        # Raising an error is often better for catching unexpected event types.
        # However, for a very basic demo, one might choose to log and ignore.
        # Let's raise an error for stricter processing.
        raise ProcessingError(f"Unknown event_type '{event.event_type}' for event: {event.event_id}")
