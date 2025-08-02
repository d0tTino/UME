"""Simple event classification utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

import logging

from ..event import Event
from .plugins import Classifier, get_classifier, register_classifier
from .finance_client import FinanceClient, FinanceClientError

logger = logging.getLogger(__name__)


@dataclass
class TagResult:
    """Represents a classification tag with an associated confidence."""

    tag: str
    confidence: float


class KeywordClassifier:
    """Classifier that tags events based on keyword matches in string values."""

    def __init__(self) -> None:
        self.keywords = {
            "malware": "malware",
            "phishing": "phishing",
            "threat": "threat",
        }

    def classify(self, payload: dict[str, Any]) -> List[TagResult]:
        results: List[TagResult] = []

        def check_text(text: str) -> None:
            lower = text.lower()
            for key, tag in self.keywords.items():
                if key in lower:
                    results.append(TagResult(tag=tag, confidence=1.0))

        for value in payload.values():
            if isinstance(value, str):
                check_text(value)

        attrs = payload.get("attributes")
        if isinstance(attrs, dict):
            for value in attrs.values():
                if isinstance(value, str):
                    check_text(value)

        return results


# Register the default classifier for generic use
register_classifier("default", KeywordClassifier())


def classify_event(event: Event) -> List[TagResult]:
    """Classify an event and return tag results using registered classifiers."""

    classifier: Classifier | None = get_classifier(event.event_type)
    if classifier is None:
        classifier = get_classifier("default")
    results: List[TagResult] = []
    if classifier is not None:
        results = classifier.classify(event.payload)

    # Detect financial transactions and categorise via finance-engine
    payload = event.payload
    transaction = payload.get("transaction")
    if not transaction:
        attrs = payload.get("attributes")
        if isinstance(attrs, dict):
            transaction = attrs.get("transaction")
    if isinstance(transaction, dict):
        try:
            with FinanceClient() as client:
                categories = client.categorize(transaction)
            results.extend(
                TagResult(tag=f"finance:{c.lower().replace(' ', '_')}", confidence=1.0)
                for c in categories
            )
        except FinanceClientError as exc:  # pragma: no cover - network failures
            logger.warning("Finance engine categorisation failed: %s", exc)

    return results
