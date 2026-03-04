from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Mapping

from ...schema_utils import validate_event_dict

try:  # pragma: no cover - optional integration dependency
    from confluent_kafka.schema_registry import Schema, SchemaRegistryClient
    from confluent_kafka.schema_registry.json_schema import JSONDeserializer, JSONSerializer
except Exception:  # pragma: no cover - optional integration dependency
    Schema = None
    SchemaRegistryClient = None
    JSONDeserializer = None
    JSONSerializer = None


def adapt_kafka_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(deepcopy(payload))
    if "nodeId" in normalized and "node_id" not in normalized:
        normalized["node_id"] = normalized["nodeId"]
    if "targetNodeId" in normalized and "target_node_id" not in normalized:
        normalized["target_node_id"] = normalized["targetNodeId"]
    return normalized


class KafkaContractValidator:
    """Validate events through schema registry when configured, else local schemas."""

    def __init__(self, schema_registry_url: str | None = None) -> None:
        self._url = schema_registry_url
        self._registry = None
        if schema_registry_url and SchemaRegistryClient is not None:
            self._registry = SchemaRegistryClient({"url": schema_registry_url})

    @property
    def using_registry(self) -> bool:
        return self._registry is not None

    def validate_for_producer(self, event_dict: Mapping[str, Any], *, subject: str) -> None:
        if self._registry is not None and Schema is not None and JSONSerializer is not None:
            schema_text = self._lookup_subject_schema(subject)
            serializer = JSONSerializer(
                json.dumps(schema_text),
                self._registry,
                lambda value, _: dict(value),
            )
            serializer(dict(event_dict), None)
            return
        validate_event_dict(dict(event_dict))

    def validate_for_consumer(self, payload: bytes, *, subject: str) -> dict[str, Any]:
        if self._registry is not None and Schema is not None and JSONDeserializer is not None:
            schema_text = self._lookup_subject_schema(subject)
            deserializer = JSONDeserializer(json.dumps(schema_text), from_dict=lambda obj, _: obj)
            parsed = deserializer(payload, None)
            if not isinstance(parsed, dict):
                raise ValueError("Schema registry deserializer did not return an object")
            return parsed
        parsed = json.loads(payload.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("Kafka payload must be a JSON object")
        validate_event_dict(parsed)
        return parsed

    def _lookup_subject_schema(self, subject: str) -> dict[str, Any]:
        if self._registry is None:
            raise ValueError("Schema Registry client is not configured")
        registered = self._registry.get_latest_version(subject)
        schema_str = registered.schema.schema_str
        loaded = json.loads(schema_str)
        if not isinstance(loaded, dict):
            raise ValueError("Schema registry subject does not contain a JSON object schema")
        return loaded
