# mypy: ignore-errors
"""Stubbed Presidio analyzer for detecting simple PII in tests."""

from __future__ import annotations
from dataclasses import dataclass
from typing import List
import json

@dataclass
class RecognizerResult:
    entity_type: str
    start: int
    end: int
    score: float

class AnalyzerEngine:
    """Very small stub of Presidio's AnalyzerEngine.

    It performs basic detection of a handful of PII types so tests which rely
    on automatic redaction have something to work with. Only ``email``,
    ``phone`` and ``ssn`` keys are recognised and the returned ``start`` and
    ``end`` offsets are not exact – tests simply check that a result is
    returned, not the offsets themselves.
    """

    def analyze(self, text: str, language: str = "en") -> List[RecognizerResult]:
        try:
            data = json.loads(text)
        except Exception:
            return []

        results: List[RecognizerResult] = []
        if isinstance(data, dict):
            email = data.get("email")
            if isinstance(email, str) and "@" in email:
                results.append(RecognizerResult("EMAIL_ADDRESS", 0, len(email), 1.0))

            phone = data.get("phone")
            if isinstance(phone, str) and any(ch.isdigit() for ch in phone):
                results.append(RecognizerResult("PHONE_NUMBER", 0, len(phone), 1.0))

            ssn = data.get("ssn")
            if isinstance(ssn, str) and len(ssn.split("-")) == 3:
                results.append(RecognizerResult("US_SSN", 0, len(ssn), 1.0))

        return results
