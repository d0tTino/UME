from types import SimpleNamespace

from ume import privacy_agent

class FakeAnalyzer:
    def analyze(self, text: str, language: str = "en"):
        return [object()]  # non empty results

class FakeAnonymizer:
    def anonymize(self, text: str, analyzer_results):
        return SimpleNamespace(text="not-json")


def test_redact_event_payload_invalid_json(monkeypatch):
    monkeypatch.setattr(privacy_agent, "_ANALYZER", FakeAnalyzer())
    monkeypatch.setattr(privacy_agent, "_ANONYMIZER", FakeAnonymizer())
    payload = {"field": "value"}
    redacted, flag = privacy_agent.redact_event_payload(payload)  # type: ignore[arg-type]
    assert redacted == payload
    assert flag is False
