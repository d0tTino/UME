from dataclasses import asdict

from ume.event import Event, EventType
from ume.classification.service import classify_event
from ume.anomaly_detection import AnomalyDetector


def _make_event(source: str, payload: dict[str, object]) -> Event:
    return Event(event_type=EventType.CREATE_NODE, timestamp=0, payload=payload, source=source)


def test_no_anomaly_within_threshold(finance_engine_mock) -> None:
    detector = AnomalyDetector(threshold=0.5)
    e1 = _make_event("entity", {"transaction": {"amount": 1}})
    e1.payload["classification"] = [asdict(r) for r in classify_event(e1)]
    assert detector.process_event(e1) is None
    e2 = _make_event("entity", {"transaction": {"amount": 2}})
    e2.payload["classification"] = [asdict(r) for r in classify_event(e2)]
    assert detector.process_event(e2) is None


def test_emits_anomaly_when_threshold_exceeded(
    finance_engine_mock, tino_storm_mock
) -> None:
    detector = AnomalyDetector(threshold=0.1)
    e1 = _make_event("entity", {"transaction": {"amount": 1}})
    e1.payload["classification"] = [asdict(r) for r in classify_event(e1)]
    detector.process_event(e1)
    e2 = _make_event("entity", {"transaction": {"amount": 2}})
    e2.payload["classification"] = [asdict(r) for r in classify_event(e2)]
    detector.process_event(e2)
    e3 = _make_event("entity", {"attributes": {"content": "some text"}})
    e3.payload["classification"] = [asdict(r) for r in classify_event(e3)]
    anomaly = detector.process_event(e3)
    assert anomaly is not None
    assert anomaly.event_type == EventType.ANOMALY_DETECTED
    assert anomaly.payload["tags"] == ["research:ml:low"]

