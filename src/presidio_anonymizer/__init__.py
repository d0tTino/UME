# mypy: ignore-errors
from __future__ import annotations
import json

class AnonymizerEngine:
    """Simplified anonymizer that replaces detected PII with placeholders."""

    def anonymize(self, text: str, analyzer_results):
        try:
            data = json.loads(text)
        except Exception:
            return type("Result", (), {"text": text})()

        if isinstance(data, dict):
            for result in analyzer_results or []:
                if result.entity_type == "EMAIL_ADDRESS" and "email" in data:
                    data["email"] = "<EMAIL_ADDRESS>"
                elif result.entity_type == "PHONE_NUMBER" and "phone" in data:
                    data["phone"] = "<PHONE_NUMBER>"
                elif result.entity_type == "US_SSN" and "ssn" in data:
                    data["ssn"] = "<SSN>"

        return type("Result", (), {"text": json.dumps(data)})()
