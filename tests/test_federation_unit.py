import json
import ume.federation as federation
from ume.federation import ClusterReplicator, MirrorMakerDriver


class DummyProducer:
    def __init__(self, conf=None):
        self.produced: list[tuple[str, bytes]] = []
        self.flushed = False

    def produce(self, topic: str, value: bytes) -> None:
        self.produced.append((topic, value))

    def flush(self) -> None:
        self.flushed = True


class DummyConsumer:
    def __init__(self, messages: list[object]):
        self.messages = messages

    def subscribe(self, topics: list[str]) -> None:  # pragma: no cover - simple stub
        self.topics = topics

    def poll(self, timeout: float = 0.1):
        return self.messages.pop(0) if self.messages else None

    def close(self) -> None:  # pragma: no cover - simple stub
        pass


class DummyMessage:
    def __init__(self, value: bytes, error: Exception | None = None) -> None:
        self._value = value
        self._error = error

    def value(self) -> bytes:
        return self._value

    def error(self):
        return self._error


class DummySettings:
    KAFKA_BOOTSTRAP_SERVERS = "local:9092"
    KAFKA_RAW_EVENTS_TOPIC = "raw"


def test_cluster_replicator_replicate_once(monkeypatch):
    event_data = {
        "event_type": "CREATE_NODE",
        "timestamp": 1,
        "payload": {},
        "node_id": "n1",
    }
    msg = DummyMessage(json.dumps(event_data).encode("utf-8"))

    consumer = DummyConsumer([msg])
    producer = DummyProducer()
    monkeypatch.setattr(federation, "Consumer", lambda conf: consumer)
    monkeypatch.setattr(federation, "Producer", lambda conf: producer)

    replicator = ClusterReplicator(DummySettings(), "peer:9092")

    replicator.replicate_once()

    assert producer.produced == [("raw", json.dumps(event_data).encode("utf-8"))]
    assert producer.flushed


def test_mirror_maker_driver_status():
    mm = MirrorMakerDriver("a", "b", ["t"])

    assert mm.status() == "stopped"

    class DummyProcess:
        def __init__(self, ret=None):
            self.ret = ret

        def poll(self):
            return self.ret

    mm._process = DummyProcess()
    assert mm.status() == "running"

    mm._process = DummyProcess(ret=0)
    assert mm.status() == "stopped"
