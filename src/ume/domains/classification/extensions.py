"""Classification extension hooks."""

from __future__ import annotations

from ...classification import classify_event
from ...kernel.policy import PolicyContext


def apply_classification(context: PolicyContext) -> dict[str, int]:
    """Annotate event payload with classification metadata."""

    event = context.effective_event
    if event is None:
        return {}
    tag_results = classify_event(event)
    event.payload["classification"] = [
        {
            "tag": r.tag,
            "confidence": r.confidence,
            "domain": r.domain,
            "subdomain": r.subdomain,
            "sensitivity": r.sensitivity,
        }
        for r in tag_results
    ]
    if tag_results:
        attributes = event.payload.setdefault("attributes", {})
        attributes["tags"] = [r.tag for r in tag_results]
        attributes["tag_confidence"] = [r.confidence for r in tag_results]
        for result in tag_results:
            if result.domain and "domain" not in attributes:
                attributes["domain"] = result.domain
            if result.subdomain and "subdomain" not in attributes:
                attributes["subdomain"] = result.subdomain
            if result.sensitivity and "sensitivity" not in attributes:
                attributes["sensitivity"] = result.sensitivity
    return {"classification_count": len(tag_results)}
