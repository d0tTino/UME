# mypy: ignore-errors
import json
import importlib.util
from pathlib import Path
import sys

module_path = Path(__file__).resolve().parents[1] / "src" / "ume" / "producer_demo.py"
spec = importlib.util.spec_from_file_location("ume.producer_demo", module_path)
assert spec and spec.loader
producer_demo = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = producer_demo
spec.loader.exec_module(producer_demo)


class DummyProducer:
    def __init__(self, conf):
        self.conf = conf
        self.produced = []

    def produce(self, topic, value, callback=None):
        self.produced.append((topic, value))
        if callback is not None:
            callback(None, type("Msg", (), {"topic": lambda self: topic, "partition": lambda self: 0, "offset": lambda self: 1})())

    def flush(self):
        return None


def test_producer_demo_emits_schema_valid_create_node(monkeypatch):
    holder = {}

    def _producer_factory(conf):
        p = DummyProducer(conf)
        holder["producer"] = p
        return p

    monkeypatch.setattr(producer_demo, "Producer", _producer_factory)

    producer_demo.main()

    produced = holder["producer"].produced
    assert produced
    topic, raw = produced[0]
    assert topic == producer_demo.TOPIC

    event = json.loads(raw.decode("utf-8"))
    assert event["eventType"] == "CREATE_NODE"
    assert event["nodeId"] == "demo_node_1"
    assert event["payload"]["node_id"] == "demo_node_1"
