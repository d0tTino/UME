"""Demonstrates AutoDev -> UME -> Culture.ai event flow using :class:`UMEClient`."""

import logging
from ume.logging_utils import configure_logging
import time

from ume import Event, EventType
from ume.client import UMEClient
from ume.config import Settings

# Configure logging so we can observe the flow
configure_logging()
logger = logging.getLogger("agent_integration")


def autodev_produce_event(client: UMEClient) -> None:
    """Simulate AutoDev emitting an event into UME."""
    event = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=int(time.time()),
        payload={"node_id": "agent1", "attributes": {"name": "AutoDev Agent"}},
        source="autodev",
    )
    logger.info("Sending event %s", event)
    client.produce_event(event)


def forward_to_culture(events) -> None:
    """Placeholder step forwarding events to Culture.ai."""
    for event in events:
        logger.info("Forwarding event %s to Culture.ai", event.event_id)
        # In a real setup you would send an HTTP request here, e.g.:
        # requests.post("https://api.culture.ai/events", json={...})


if __name__ == "__main__":
    settings = Settings()
    client = UMEClient(settings)

    # Step 1: AutoDev produces an event
    autodev_produce_event(client)

    # Step 2: UMEClient consumes events for further processing
    consumed = list(client.consume_events())

    # Step 3: Forward those events to Culture.ai (simulated)
    forward_to_culture(consumed)
