from fastapi.testclient import TestClient
import json
import pytest

from ume.ingestion_api import app, settings
import ume.ingestion_api as ingestion_api
from ume.metrics import INGEST_EVENTS_TOTAL


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
    object.__setattr__(settings, "UME_INGEST_LENIENT_VALIDATION", False)
    INGEST_EVENTS_TOTAL.clear()
    with TestClient(app) as test_client:
        yield test_client, prod
    INGEST_EVENTS_TOTAL.clear()


def _ingest_event_count(event_type: str) -> float:
    for metric in INGEST_EVENTS_TOTAL.collect():
        for sample in metric.samples:
            if sample.name.endswith("_total") and sample.labels.get("event_type") == event_type:
                return float(sample.value)
    return 0.0


def test_post_event_publishes_to_kafka(client):
    test_client, prod = client
    event = {
        "eventType": "CREATE_NODE",
        "timestamp": "2023-01-01T00:00:00Z",
        "node_id": "n1",
        "payload": {},
    }

    res = test_client.post("/events", json=event)
    assert res.status_code == 202
    assert prod.produced == [
        (settings.KAFKA_RAW_EVENTS_TOPIC, json.dumps(event).encode("utf-8"))
    ]
    assert prod.poll_calls == 1
    assert _ingest_event_count("create_node") == 1


def test_invalid_event_returns_400_in_strict_mode(client):
    test_client, prod = client
    res = test_client.post("/events", json={"eventType": "CREATE_NODE"})
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "event validation failed"
    assert prod.produced == []
    assert _ingest_event_count("create_node") == 0


def test_invalid_event_quarantined_in_lenient_mode(client):
    test_client, prod = client
    object.__setattr__(settings, "UME_INGEST_LENIENT_VALIDATION", True)

    bad_event = {"eventType": "CREATE_NODE"}
    res = test_client.post("/events", json=bad_event)

    assert res.status_code == 202
    assert res.json() == {"status": "quarantined"}
    assert len(prod.produced) == 1
    produced_topic, produced_payload = prod.produced[0]
    assert produced_topic == settings.KAFKA_QUARANTINE_TOPIC
    quarantine_payload = json.loads(produced_payload.decode("utf-8"))
    assert quarantine_payload["event"] == bad_event
    assert quarantine_payload["ingestion"] == {
        "mode": "lenient",
        "reason": "validation_failed",
    }
    assert quarantine_payload["error"]["error"] == "event validation failed"
    assert _ingest_event_count("create_node") == 1
