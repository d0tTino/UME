import json
from pathlib import Path

import pytest

from ume.anonymizer import anonymize_email
from ume.pipeline import privacy_agent


PII_SAMPLES = json.loads(Path("tests/data/pii_samples.json").read_text())


def test_anonymize_email_basic():
    payload = {"email": "user@example.com"}
    result, flag = anonymize_email(payload)
    assert flag is True
    assert (
        result["email"]
        == "b4c9a289323b21a01c3e940f150eb9b8c542587f1abfd8f0e1cc1ffc5e475514"
    )


@pytest.mark.parametrize("payload", PII_SAMPLES)
def test_redact_payload_false_negatives(payload):
    redacted, flag = privacy_agent.redact_event_payload(payload)
    assert flag is True, f"Payload not redacted: {payload}"
    assert redacted != payload
