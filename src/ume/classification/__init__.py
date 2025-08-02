"""Classification utilities."""

from .plugins import Classifier, register_classifier
from .service import classify_event, TagResult

__all__ = ["classify_event", "TagResult", "Classifier", "register_classifier"]
