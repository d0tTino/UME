from presidio_analyzer import RecognizerResult
from ume import privacy_agent


class FakeAnalyzer:
    def __init__(self, results):
        self._results = results

    def analyze(self, text: str, language: str = "en"):
        return self._results


def test_redact_event_payload_with_pii(monkeypatch):
    payload = {"email": "user@example.com"}
    results = [RecognizerResult(entity_type="EMAIL_ADDRESS", start=11, end=27, score=1.0)]
    monkeypatch.setattr(privacy_agent, "_ANALYZER", FakeAnalyzer(results))
    redacted, flag = privacy_agent.redact_event_payload(payload)
    assert flag is True
    assert redacted == {"email": "<EMAIL_ADDRESS>"}


def test_redact_event_payload_without_pii(monkeypatch):
    payload = {"message": "hello"}
    monkeypatch.setattr(privacy_agent, "_ANALYZER", FakeAnalyzer([]))
    redacted, flag = privacy_agent.redact_event_payload(payload)
    assert flag is False
    assert redacted == payload
