"""Plugin utilities for event classification."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - used for type hints only
    from .service import TagResult


class Classifier(Protocol):
    """Protocol for classification plugins."""

    def classify(self, payload: dict[str, Any]) -> List["TagResult"]:
        """Return classification results for the provided payload."""


_registry: Dict[str, Classifier] = {}


def register_classifier(event_type: str, classifier: Classifier) -> None:
    """Register a classifier for a specific event type."""

    _registry[event_type] = classifier


def get_classifier(event_type: str) -> Optional[Classifier]:
    """Retrieve the classifier registered for ``event_type`` if any."""

    return _registry.get(event_type)


__all__ = ["Classifier", "register_classifier", "get_classifier"]

