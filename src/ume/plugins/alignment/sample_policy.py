"""Sample alignment plugin demonstrating policy enforcement."""

from ...event import Event, EventType
from . import AlignmentPlugin, PolicyViolationError, register_plugin


class DenyForbiddenNode(AlignmentPlugin):
    """Reject CREATE_NODE events for the special node_id 'forbidden'."""

    def validate(self, event: Event) -> None:
        if event.event_type == EventType.CREATE_NODE and event.payload.get("node_id") == "forbidden":
            raise PolicyViolationError("Creation of node_id 'forbidden' is not allowed")


# Register plugin instance on import
register_plugin(DenyForbiddenNode())
