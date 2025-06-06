# src/ume/processing.py
from .event import Event, EventType
from .graph_adapter import IGraphAdapter  # Use IGraphAdapter
from .listeners import get_registered_listeners


class ProcessingError(ValueError):
    """Custom exception for event processing errors."""

    pass


def apply_event_to_graph(event: Event, graph: IGraphAdapter) -> None:
    """
    Applies an event to a graph, modifying the graph based on event type and payload.

    This function uses the IGraphAdapter interface to interact with the graph,
    allowing for different graph backend implementations.
    Supported event_types:
    - "CREATE_NODE": Creates a new node. Requires `event.payload` to contain
      `node_id` (str) and `attributes` (dict).
    - "UPDATE_NODE_ATTRIBUTES": Updates an existing node's attributes. Requires
      `event.payload` to contain `node_id` (str) and `attributes` (non-empty dict).
    - "CREATE_EDGE": Creates a directed, labeled edge between two existing nodes.
      Requires `event.node_id` (source), `event.target_node_id` (target), and
      `event.label` (all strings).
    - "DELETE_EDGE": Removes a specific edge. Requires `event.node_id` (source),
      `event.target_node_id` (target), and `event.label` (all strings).

    Args:
        event (Event): The Event object to apply, with fields validated by `parse_event`.
        graph (IGraphAdapter): An instance implementing the IGraphAdapter interface.

    Raises:
        ProcessingError: If fields validated by `parse_event` are unexpectedly invalid
                         (e.g. None when str expected for a given event type),
                         if event payload is missing required fields for the event_type,
                         or if the event_type is unknown and not handled.
                         Also raised by graph adapter methods for graph consistency issues
                         (e.g., node already exists for CREATE_NODE, node not found for UPDATE_NODE_ATTRIBUTES/CREATE_EDGE).
    """
    if event.event_type == EventType.CREATE_NODE:
        node_id = event.payload.get("node_id")
        if not node_id:
            raise ProcessingError(
                f"Missing 'node_id' in payload for CREATE_NODE event: {event.event_id}"
            )
        if not isinstance(node_id, str):
            raise ProcessingError(
                f"'node_id' must be a string for CREATE_NODE event: {event.event_id}"
            )

        attributes = event.payload.get(
            "attributes", {}
        )  # Default to empty dict if 'attributes' key is missing
        if not isinstance(
            attributes, dict
        ):  # Ensure attributes, if provided, is a dict
            raise ProcessingError(
                f"'attributes' must be a dictionary for CREATE_NODE event, if provided. Got: {type(attributes).__name__} for event: {event.event_id}"
            )

        graph.add_node(node_id, attributes)  # Call adapter's add_node
        for listener in get_registered_listeners():
            listener.on_node_created(node_id, attributes)

    elif event.event_type == EventType.UPDATE_NODE_ATTRIBUTES:
        node_id = event.payload.get("node_id")
        if not node_id:
            raise ProcessingError(
                f"Missing 'node_id' in payload for UPDATE_NODE_ATTRIBUTES event: {event.event_id}"
            )
        if not isinstance(node_id, str):
            raise ProcessingError(
                f"'node_id' must be a string for UPDATE_NODE_ATTRIBUTES event: {event.event_id}"
            )

        if "attributes" not in event.payload:
            raise ProcessingError(
                f"Missing 'attributes' key in payload for UPDATE_NODE_ATTRIBUTES event: {event.event_id}"
            )

        attributes = event.payload["attributes"]
        if not isinstance(attributes, dict):
            raise ProcessingError(
                f"'attributes' must be a dictionary for UPDATE_NODE_ATTRIBUTES event: {event.event_id}"
            )
        if not attributes:
            raise ProcessingError(
                f"'attributes' dictionary cannot be empty for UPDATE_NODE_ATTRIBUTES event: {event.event_id}"
            )

        graph.update_node(node_id, attributes)  # Call adapter's update_node
        for listener in get_registered_listeners():
            listener.on_node_updated(node_id, attributes)

    elif event.event_type == EventType.CREATE_EDGE:
        # parse_event should have validated presence and type of node_id, target_node_id, label
        source_node_id = event.node_id
        target_node_id = event.target_node_id
        label = event.label

        # Defensive checks in case an improperly constructed Event is passed
        if not (
            isinstance(source_node_id, str)
            and isinstance(target_node_id, str)
            and isinstance(label, str)
        ):
            raise ProcessingError(
                f"Invalid event structure for CREATE_EDGE: source_node_id (event.node_id), target_node_id, "
                f"and label must be strings and present. Event ID: {event.event_id}"
            )

        # After the defensive check above, mypy still treats these variables as
        # Optional[str]. Use assertions to convince the type checker they are
        # indeed strings before passing them to the adapter methods.

        assert isinstance(source_node_id, str)
        assert isinstance(target_node_id, str)
        assert isinstance(label, str)
        graph.add_edge(source_node_id, target_node_id, label)
        for listener in get_registered_listeners():
            listener.on_edge_created(source_node_id, target_node_id, label)

    elif event.event_type == EventType.DELETE_EDGE:
        # parse_event should have validated presence and type of node_id, target_node_id, label
        source_node_id = event.node_id
        target_node_id = event.target_node_id
        label = event.label

        # Defensive checks
        if not (
            isinstance(source_node_id, str)
            and isinstance(target_node_id, str)
            and isinstance(label, str)
        ):
            raise ProcessingError(
                f"Invalid event structure for DELETE_EDGE: source_node_id (event.node_id), target_node_id, "
                f"and label must be strings and present. Event ID: {event.event_id}"
            )

        # As above, assert non-None string values so mypy treats them correctly
        # in the adapter call.

        assert isinstance(source_node_id, str)
        assert isinstance(target_node_id, str)
        assert isinstance(label, str)
        graph.delete_edge(source_node_id, target_node_id, label)
        for listener in get_registered_listeners():
            listener.on_edge_deleted(source_node_id, target_node_id, label)

    else:
        # For now, we can choose to ignore unknown event types or raise an error.
        # Raising an error is often better for catching unexpected event types.
        # However, for a very basic demo, one might choose to log and ignore.
        # Let's raise an error for stricter processing.
        raise ProcessingError(
            f"Unknown event_type '{event.event_type}' for event: {event.event_id}"
        )
