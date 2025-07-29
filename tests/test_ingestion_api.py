from fastapi.testclient import TestClient
import json
import pytest

from ume.ingestion_api import app, settings
import ume.ingestion_api as ingestion_api


class FakeProducer:
    def __init__(self):
        self.produced = []
        self.poll_calls = 0
        self.flush_calls = 0

    def produce(self, topic, value):
        self.produced.append((topic, value))

    def poll(self, timeout):
        self.poll_calls += 1

    def flush(self):
        self.flush_calls += 1


@pytest.fixture
def client(monkeypatch):
    prod = FakeProducer()
    monkeypatch.setattr(ingestion_api, "Producer", lambda conf: prod)
    with TestClient(app) as test_client:
        yield test_client, prod


def test_post_event_publishes_to_kafka(client):
    test_client, prod = client
    event = {"eventType": "CREATE_NODE", "timestamp": 1, "node_id": "n1", "payload": {}}

    res = test_client.post("/events", json=event)
    assert res.status_code == 202
    assert prod.produced == [
        (settings.KAFKA_RAW_EVENTS_TOPIC, json.dumps(event).encode("utf-8"))
    ]
    assert prod.poll_calls == 1


def test_invalid_event_returns_400(client):
    test_client, prod = client
    res = test_client.post("/events", json={"eventType": "CREATE_NODE"})
    assert res.status_code == 400
    assert prod.produced == []

