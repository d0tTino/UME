"""Simple event classification utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ..event import Event


@dataclass
class TagResult:
    """Represents a classification tag with an associated confidence."""

    tag: str
    confidence: float


def classify_event(event: Event) -> List[TagResult]:
    """Classify an event and return tag results.

    This rudimentary implementation looks for specific keywords in any
    string values found in the event's payload or attribute dictionary.
    If a keyword is present, a tag is emitted with a confidence score of 1.0.
    """

    keywords = {
        "malware": "malware",
        "phishing": "phishing",
        "threat": "threat",
    }

    results: List[TagResult] = []

    def check_text(text: str) -> None:
        lower = text.lower()
        for key, tag in keywords.items():
            if key in lower:
                results.append(TagResult(tag=tag, confidence=1.0))

    payload = event.payload
    for value in payload.values():
        if isinstance(value, str):
            check_text(value)

    attrs = payload.get("attributes")
    if isinstance(attrs, dict):
        for value in attrs.values():
            if isinstance(value, str):
                check_text(value)

    return results
