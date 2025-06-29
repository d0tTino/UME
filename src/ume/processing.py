# src/ume/processing.py
# Use IGraphAdapter
from __future__ import annotations
from typing import Optional

from .event import Event
from .graph_adapter import IGraphAdapter
from .policy import PolicyEvaluationError, RegoPolicyMiddleware
# MockGraph import removed as it's no longer directly used for type hinting here


class ProcessingError(ValueError):
    """Custom exception for event processing errors."""

    pass


def apply_event_to_graph(
    event: Event,
    graph: IGraphAdapter,
    policy: Optional[RegoPolicyMiddleware] = None,
) -> None:
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
    if policy is not None:
        try:
            allowed = policy.allows(event, graph)
        except PolicyEvaluationError as exc:  # noqa: PERF203
            raise ProcessingError(str(exc)) from exc
        if not allowed:
            raise ProcessingError(
                f"Event {event.event_type} blocked by policy"
            )

    if event.event_type == "CREATE_NODE":
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

    elif event.event_type == "UPDATE_NODE_ATTRIBUTES":
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

    elif event.event_type == "CREATE_EDGE":
        # parse_event should have validated presence and type of node_id, target_node_id, label
        source_node_id = event.node_id
        target_node_id = event.target_node_id
        label = event.label

        # Defensive checks, though parse_event should ensure these are strings for this event type
        if not all(
            isinstance(val, str) for val in [source_node_id, target_node_id, label]
        ):
            raise ProcessingError(
                f"Invalid event structure for CREATE_EDGE: source_node_id (event.node_id), target_node_id, "
                f"and label must be strings and present. Event ID: {event.event_id}"
            )
        assert isinstance(source_node_id, str)
        assert isinstance(target_node_id, str)
        assert isinstance(label, str)
        graph.add_edge(source_node_id, target_node_id, label)

    elif event.event_type == "DELETE_EDGE":
        # parse_event should have validated presence and type of node_id, target_node_id, label
        source_node_id = event.node_id
        target_node_id = event.target_node_id
        label = event.label

        # Defensive checks
        if not all(
            isinstance(val, str) for val in [source_node_id, target_node_id, label]
        ):
            raise ProcessingError(
                f"Invalid event structure for DELETE_EDGE: source_node_id (event.node_id), target_node_id, "
                f"and label must be strings and present. Event ID: {event.event_id}"
            )
        assert isinstance(source_node_id, str)
        assert isinstance(target_node_id, str)
        assert isinstance(label, str)
        graph.delete_edge(source_node_id, target_node_id, label)

    else:
        # For now, we can choose to ignore unknown event types or raise an error.
        # Raising an error is often better for catching unexpected event types.
        # However, for a very basic demo, one might choose to log and ignore.
        # Let's raise an error for stricter processing.
        raise ProcessingError(
            f"Unknown event_type '{event.event_type}' for event: {event.event_id}"
        )
