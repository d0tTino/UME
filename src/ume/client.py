from __future__ import annotations

import json
import logging
from types import TracebackType
from typing import Iterator, Any

from confluent_kafka import Consumer, Producer, KafkaError
from jsonschema import ValidationError
from .config import Settings

from .event import Event, EventError, parse_event, EventType
from .schema_utils import validate_event_dict
from .processing import DEFAULT_VERSION
from .proto import events_pb2
from google.protobuf import struct_pb2
from google.protobuf.json_format import MessageToDict


class UMEClientError(Exception):
    """Exception raised for errors occurring within :class:`UMEClient`."""

    pass


logger = logging.getLogger(__name__)


class UMEClient:
    """Simple Kafka-based client for producing and consuming UME events."""

    def __init__(self, settings: Settings, *, use_protobuf: bool = False) -> None:
        self.produce_topic = settings.KAFKA_RAW_EVENTS_TOPIC
        self.consume_topic = settings.KAFKA_CLEAN_EVENTS_TOPIC
        bootstrap = settings.KAFKA_BOOTSTRAP_SERVERS
        group_id = settings.KAFKA_GROUP_ID
        self.producer = Producer({"bootstrap.servers": bootstrap})
        self.use_protobuf = use_protobuf
        self.consumer = Consumer(
            {
                "bootstrap.servers": bootstrap,
                "group.id": group_id,
                "auto.offset.reset": "earliest",
            }
        )
        self.consumer.subscribe([self.consume_topic])

    def produce_event(self, event: Event) -> None:
        """Serialize and send an Event to the configured topic."""
        data_dict = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp,
            "payload": event.payload,
            "source": event.source,
            "node_id": event.node_id,
            "target_node_id": event.target_node_id,
            "label": event.label,
        }
        try:
            envelope_dict = {"schema_version": DEFAULT_VERSION, "event": data_dict}
            validate_event_dict(envelope_dict)
            if self.use_protobuf:
                proto_event = self._dict_to_proto(event)
                proto_envelope = events_pb2.EventEnvelope(  # type: ignore[attr-defined]
                    schema_version=DEFAULT_VERSION,
                )
                setattr(proto_envelope, proto_event[0], proto_event[1])
                self.producer.produce(self.produce_topic, proto_envelope.SerializeToString())
            else:
                self.producer.produce(
                    self.produce_topic, json.dumps(envelope_dict).encode("utf-8")
                )
            self.producer.flush()
        except ValidationError as e:
            logger.error("Event validation failed: %s", e.message)
            raise UMEClientError(f"Event validation failed: {e.message}") from e
        except (
            Exception
        ) as e:  # pragma: no cover - confluent_kafka may raise various errors
            logger.error("Failed to produce event: %s", e)
            raise UMEClientError(f"Failed to produce event: {e}") from e

    def consume_events(self, timeout: float = 1.0) -> Iterator[Event]:
        """Yield Events from the configured topic until no message is available."""
        while True:
            msg = self.consumer.poll(timeout)
            if msg is None:
                break
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    break
                raise UMEClientError(f"Consumer error: {msg.error()}")
            if self.use_protobuf:
                try:
                    envelope = events_pb2.EventEnvelope.FromString(  # type: ignore[attr-defined]
                        msg.value()
                    )
                except Exception as exc:  # pragma: no cover - malformed message
                    logger.warning("Invalid protobuf received: %s", exc)
                    continue
                event_dict = self._proto_to_dict(envelope)
                try:
                    validate_event_dict({"schema_version": envelope.schema_version, "event": event_dict})
                except ValidationError as exc:
                    logger.warning("Invalid protobuf event: %s", exc)
                    continue
            else:
                try:
                    data = json.loads(msg.value().decode("utf-8"))
                except json.JSONDecodeError as exc:  # pragma: no cover - malformed message
                    logger.warning("Invalid JSON received: %s", exc)
                    continue
                if isinstance(data, dict) and "event" in data and "schema_version" in data:
                    try:
                        validate_event_dict(data)
                    except ValidationError as exc:
                        logger.warning("Invalid JSON event: %s", exc)
                        continue
                    event_dict = data["event"]
                else:
                    event_dict = data
            payload = event_dict.get("payload")
            if isinstance(payload, dict):
                text_values = [v for v in payload.values() if isinstance(v, str)]
                if text_values:
                    try:
                        from .embedding import generate_embedding  # local import to avoid heavy dependency
                    except ImportError:
                        logger.warning(
                            "Embedding dependencies missing; skipping embedding generation"
                        )
                    else:
                        payload["embedding"] = generate_embedding(" ".join(text_values))
            try:
                event = parse_event(event_dict)
            except EventError as exc:
                logger.warning("Invalid event received: %s", exc)
                continue
            yield event

    def close(self) -> None:
        """Flush the producer and close the consumer."""
        try:
            self.producer.flush()
        finally:
            self.consumer.close()

    def __enter__(self) -> "UMEClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def _dict_to_proto(self, event: Event) -> tuple[str, Any]:
        struct_payload = struct_pb2.Struct()
        struct_payload.update(event.payload)
        meta = events_pb2.BaseEvent(  # type: ignore[attr-defined]
            event_id=event.event_id,
            event_type=event.event_type,
            timestamp=event.timestamp,
            source=event.source or "",
            node_id=event.node_id or "",
            target_node_id=event.target_node_id or "",
            label=event.label or "",
            payload=struct_payload,
        )
        if event.event_type == EventType.CREATE_NODE:
            return ("create_node", events_pb2.CreateNode(meta=meta))  # type: ignore[attr-defined]
        if event.event_type == EventType.UPDATE_NODE_ATTRIBUTES:
            return (
                "update_node_attributes",
                events_pb2.UpdateNodeAttributes(meta=meta),  # type: ignore[attr-defined]
            )
        if event.event_type == EventType.CREATE_EDGE:
            return ("create_edge", events_pb2.CreateEdge(meta=meta))  # type: ignore[attr-defined]
        if event.event_type == EventType.DELETE_EDGE:
            return ("delete_edge", events_pb2.DeleteEdge(meta=meta))  # type: ignore[attr-defined]
        raise UMEClientError(f"Unknown event type: {event.event_type}")

    def _proto_to_dict(self, envelope: Any) -> dict[str, Any]:
        if envelope.HasField("create_node"):
            meta = envelope.create_node.meta
        elif envelope.HasField("update_node_attributes"):
            meta = envelope.update_node_attributes.meta
        elif envelope.HasField("create_edge"):
            meta = envelope.create_edge.meta
        elif envelope.HasField("delete_edge"):
            meta = envelope.delete_edge.meta
        else:
            raise UMEClientError("Envelope missing payload")

        payload = MessageToDict(meta.payload)
        return {
            "event_id": meta.event_id,
            "event_type": meta.event_type,
            "timestamp": meta.timestamp,
            "payload": payload,
            "source": meta.source or None,
            "node_id": meta.node_id or None,
            "target_node_id": meta.target_node_id or None,
            "label": meta.label or None,
        }
