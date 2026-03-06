#!/usr/bin/env python3
"""Compose smoke check for projection worker graph mutations."""

from __future__ import annotations

import json
import time

from confluent_kafka import Producer

from ume.config import settings
from ume.resources import create_graph
from ume.utils import ssl_config

SMOKE_NODE_ID = "compose-smoke-node"


def _produce_smoke_event() -> None:
    conf = {"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS}
    conf.update(ssl_config())
    producer = Producer(conf)
    event = {
        "eventType": "CREATE_NODE",
        "eventId": "compose-smoke-event-1",
        "timestamp": int(time.time()),
        "nodeId": SMOKE_NODE_ID,
        "payload": {"type": "SmokeCheck", "source": "compose"},
    }
    producer.produce(settings.KAFKA_CLEAN_EVENTS_TOPIC, json.dumps(event).encode("utf-8"))
    producer.flush()


def _wait_for_projection(timeout_s: float = 20.0) -> dict | None:
    graph = create_graph()
    try:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            node = graph.get_node(SMOKE_NODE_ID)
            if node is not None:
                return node
            time.sleep(0.5)
    finally:
        close = getattr(graph, "close", None)
        if callable(close):
            close()
    return None


def main() -> int:
    _produce_smoke_event()
    node = _wait_for_projection()
    if node is None:
        raise SystemExit("compose smoke check failed: projection side effect not observed")
    print(f"compose smoke check passed: projected node {SMOKE_NODE_ID} -> {node}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
