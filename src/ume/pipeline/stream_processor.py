"""Faust-based stream processor for UME events."""

from __future__ import annotations

try:
    import faust
    from faust.types import StreamT
except Exception:  # pragma: no cover - optional dependency missing
    faust = None  # type: ignore[assignment]
    StreamT = object  # type: ignore[assignment]
import json

from ume import EventError, parse_event

from ..config import settings
from ..events.contract import canonicalize_event
from .router import route_event, router_config_from_settings

IN_TOPIC = settings.KAFKA_CLEAN_EVENTS_TOPIC


def build_app(broker: str = settings.KAFKA_BOOTSTRAP_SERVERS):
    """Create a Faust App instance."""
    if faust is None:  # pragma: no cover - optional dependency missing
        raise RuntimeError("faust-streaming is not installed")

    router_config = router_config_from_settings()
    app = faust.App("ume_stream_processor", broker=broker)
    app.conf.web_enabled = False

    source_topic = app.topic(IN_TOPIC, value_type=bytes)
    topic_by_name = {
        topic_name: app.topic(topic_name, value_type=bytes)
        for topic_name in {
            router_config.node_topic,
            router_config.edge_topic,
            router_config.default_topic,
            router_config.dead_letter_topic,
        }
    }

    @app.agent(source_topic)  # type: ignore[misc]
    async def _process(stream: StreamT[bytes]) -> None:
        async for raw in stream:
            try:
                data = json.loads(raw.decode("utf-8"))
                canonical = canonicalize_event(data)
                parse_event(canonical)
            except (ValueError, EventError, json.JSONDecodeError):
                continue

            decision = route_event(canonical, router_config)
            topic = topic_by_name.get(decision.topic)
            if topic is None:
                topic = app.topic(decision.topic, value_type=bytes)
                topic_by_name[decision.topic] = topic
            await topic.send(value=raw)

    return app


app = build_app() if faust is not None else None


def main() -> None:
    app.main()


if __name__ == "__main__":
    main()
