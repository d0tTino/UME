"""Faust-based stream processor for UME events."""

from __future__ import annotations

try:
    import faust
    from faust.types import StreamT
except Exception:  # pragma: no cover - optional dependency missing
    faust = None  # type: ignore[assignment]
    StreamT = object  # type: ignore[assignment]
import json
from typing import Any, Mapping

from ..config import settings
from .core import EventPipelineOrchestrator, PipelineOutcome
from .router import route_event, router_config_from_settings

IN_TOPIC = settings.KAFKA_CLEAN_EVENTS_TOPIC


def _outbound_payload(
    envelope,
    *,
    family: str,
    schema_version: str | None,
    policy_result: str | None,
    topic: str,
    reason: str,
) -> dict[str, Any]:
    canonical = envelope.canonical_event
    if isinstance(canonical, Mapping):
        payload: dict[str, Any] = dict(canonical)
    else:
        payload = {
            "metadata": {
                "event_type": envelope.event_type or "UNKNOWN_EVENT",
                "timestamp": None,
            },
            "graph": {},
            "dlq": {
                "stage": envelope.stage,
                "reason": envelope.reason,
                "details": envelope.details,
            },
        }

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        payload["metadata"] = metadata

    metadata["policy_result"] = policy_result or envelope.outcome.value
    metadata["schema_version"] = (
        schema_version or metadata.get("schema_version") or "unknown"
    )
    metadata["type_family"] = family or metadata.get("type_family") or "unknown"
    metadata["routing"] = {
        "topic": topic,
        "reason": reason,
        "family": family,
        "schema_version": schema_version,
        "policy_result": policy_result or envelope.outcome.value,
    }

    return payload


def build_app(broker: str = settings.KAFKA_BOOTSTRAP_SERVERS):
    """Create a Faust App instance."""
    if faust is None:  # pragma: no cover - optional dependency missing
        raise RuntimeError("faust-streaming is not installed")

    router_config = router_config_from_settings()
    orchestrator = EventPipelineOrchestrator()
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
            except (ValueError, json.JSONDecodeError):
                decision = route_event(
                    {
                        "metadata": {"policy_result": PipelineOutcome.REJECTED.value},
                        "graph": {},
                    },
                    router_config,
                )
                envelope_payload = {
                    "metadata": {
                        "event_type": "UNKNOWN_EVENT",
                        "timestamp": None,
                        "policy_result": PipelineOutcome.REJECTED.value,
                        "schema_version": "unknown",
                        "type_family": decision.family,
                        "routing": {
                            "topic": decision.topic,
                            "reason": decision.reason,
                            "family": decision.family,
                            "schema_version": decision.schema_version,
                            "policy_result": decision.policy_result,
                        },
                    },
                    "graph": {},
                    "dlq": {
                        "stage": "decode",
                        "reason": "malformed_json",
                        "details": {"raw_payload_present": True},
                    },
                }
                topic = topic_by_name.get(decision.topic)
                if topic is None:
                    topic = app.topic(decision.topic, value_type=bytes)
                    topic_by_name[decision.topic] = topic
                await topic.send(value=json.dumps(envelope_payload).encode("utf-8"))
                continue

            envelope = orchestrator.run(
                data,
                source="faust_stream_processor",
                adapter="kafka",
                raw_payload=raw,
            )
            canonical = envelope.canonical_event
            if isinstance(canonical, Mapping):
                routing_input = dict(canonical)
                metadata = routing_input.get("metadata")
                if not isinstance(metadata, dict):
                    metadata = {}
                    routing_input["metadata"] = metadata
                metadata["policy_result"] = envelope.outcome.value
            else:
                routing_input = {
                    "metadata": {
                        "policy_result": envelope.outcome.value,
                        "event_type": envelope.event_type,
                    },
                    "graph": {},
                }
            decision = route_event(routing_input, router_config)
            outbound_payload = _outbound_payload(
                envelope,
                family=decision.family,
                schema_version=decision.schema_version,
                policy_result=decision.policy_result,
                topic=decision.topic,
                reason=decision.reason,
            )
            topic = topic_by_name.get(decision.topic)
            if topic is None:
                topic = app.topic(decision.topic, value_type=bytes)
                topic_by_name[decision.topic] = topic
            await topic.send(value=json.dumps(outbound_payload).encode("utf-8"))

    return app


app = build_app() if faust is not None else None


def main() -> None:
    app.main()


if __name__ == "__main__":
    main()
