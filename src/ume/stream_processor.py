"""Faust-based stream processor for UME events."""

from __future__ import annotations

import faust
import json
from typing import Dict

from ume import EventType, parse_event, EventError
from .config import settings

IN_TOPIC = settings.KAFKA_CLEAN_EVENTS_TOPIC
EDGE_TOPIC = settings.KAFKA_EDGE_TOPIC
NODE_TOPIC = settings.KAFKA_NODE_TOPIC

# Map event types to destination topics
EVENT_TOPIC_MAP: Dict[str, str] = {
    EventType.CREATE_EDGE.value: EDGE_TOPIC,
    EventType.CREATE_NODE.value: NODE_TOPIC,
}


def build_app(broker: str = settings.KAFKA_BOOTSTRAP_SERVERS) -> faust.App:
    """Create a Faust App instance."""
    app = faust.App("ume_stream_processor", broker=broker)
    app.conf.web_enabled = False

    source_topic = app.topic(IN_TOPIC, value_type=bytes)
    edge_topic = app.topic(EDGE_TOPIC, value_type=bytes)
    node_topic = app.topic(NODE_TOPIC, value_type=bytes)

    @app.agent(source_topic)
    async def _process(stream):
        async for raw in stream:
            try:
                data = json.loads(raw.decode("utf-8"))
                event = parse_event(data)
            except (ValueError, EventError, json.JSONDecodeError):
                continue

            dest = EVENT_TOPIC_MAP.get(event.event_type)
            if dest == EDGE_TOPIC:
                await edge_topic.send(value=raw)
            elif dest == NODE_TOPIC:
                await node_topic.send(value=raw)

    return app


app = build_app()


def main() -> None:
    app.main()


if __name__ == "__main__":
    main()
