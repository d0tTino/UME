# src/ume/processing.py
from .event import Event
from .graph import MockGraph # Using MockGraph for now

class ProcessingError(ValueError):
    """Custom exception for event processing errors."""
    pass

def apply_event_to_graph(event: Event, graph: MockGraph) -> None:
    """
    Applies an event to a graph, modifying the graph based on event type and payload.

    This is a conceptual implementation using MockGraph for demonstration
    and testing purposes.

    Args:
        event: The Event object to apply.
        graph: The MockGraph instance to modify.

    Raises:
        ProcessingError: If the event payload is missing required fields
                         for the given event_type, or if the event_type is unknown.
    """
    if event.event_type == "CREATE_NODE":
        node_id = event.payload.get("node_id")
        attributes = event.payload.get("attributes", {})
        if not node_id:
            raise ProcessingError(f"Missing 'node_id' in payload for CREATE_NODE event: {event.event_id}")
        if not isinstance(node_id, str):
            raise ProcessingError(f"'node_id' must be a string for CREATE_NODE event: {event.event_id}")
        if graph.node_exists(node_id):
            raise ProcessingError(f"Node '{node_id}' already exists; cannot recreate with CREATE_NODE event: {event.event_id}")
        graph.add_node(node_id, attributes)

    elif event.event_type == "UPDATE_NODE_ATTRIBUTES":
        node_id = event.payload.get("node_id")
        if not node_id:
            raise ProcessingError(f"Missing 'node_id' in payload for UPDATE_NODE_ATTRIBUTES event: {event.event_id}")

        if "attributes" not in event.payload:
            raise ProcessingError(f"Missing 'attributes' key in payload for UPDATE_NODE_ATTRIBUTES event: {event.event_id}")

        attributes = event.payload["attributes"] # Key is present, now get value

        if not isinstance(attributes, dict):
            raise ProcessingError(f"'attributes' must be a dictionary for UPDATE_NODE_ATTRIBUTES event: {event.event_id}")

        if not attributes: # This checks if the dictionary is empty
            raise ProcessingError(f"'attributes' dictionary cannot be empty for UPDATE_NODE_ATTRIBUTES event: {event.event_id}")

        if not graph.node_exists(node_id):
            raise ProcessingError(f"Node '{node_id}' does not exist; cannot update attributes: {event.event_id}")

        graph.add_node(node_id, attributes) # add_node also handles updates

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
