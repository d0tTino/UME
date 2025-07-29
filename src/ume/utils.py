from typing import Any, Dict, List
import os
import re


def ssl_config() -> Dict[str, str]:
    """Return Kafka SSL configuration if cert env vars are set."""
    ca = os.environ.get("KAFKA_CA_CERT")
    cert = os.environ.get("KAFKA_CLIENT_CERT")
    key = os.environ.get("KAFKA_CLIENT_KEY")
    if ca and cert and key:
        return {
            "security.protocol": "SSL",
            "ssl.ca.location": ca,
            "ssl.certificate.location": cert,
            "ssl.key.location": key,
        }
    return {}


# ----------------------------------------------------------------------------
# Event field conversion helpers

_CAMEL_TO_SNAKE = {
    "eventId": "event_id",
    "eventType": "event_type",
    "nodeId": "node_id",
    "targetNodeId": "target_node_id",
    "schemaVersion": "schema_version",
}

_SNAKE_TO_CAMEL = {v: k for k, v in _CAMEL_TO_SNAKE.items()}


def event_to_snake(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of ``data`` with camelCase fields converted to snake_case."""
    out: Dict[str, Any] = {}
    for key, value in data.items():
        if key == "event" and isinstance(value, dict):
            out[key] = event_to_snake(value)
            continue
        out[_CAMEL_TO_SNAKE.get(key, key)] = value
    return out


def event_to_camel(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of ``data`` with snake_case fields converted to camelCase."""
    out: Dict[str, Any] = {}
    for key, value in data.items():
        if key == "event" and isinstance(value, dict):
            out[key] = event_to_camel(value)
            continue
        out[_SNAKE_TO_CAMEL.get(key, key)] = value
    return out


_TOKEN_RE = re.compile(r"\b\w+\b")


def tokenize(text: str) -> List[str]:
    """Return a list of lowercase tokens from ``text``."""
    return _TOKEN_RE.findall(text.lower())

