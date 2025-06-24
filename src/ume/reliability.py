from __future__ import annotations

from typing import Iterable, List

from .metrics import FALSE_TEXT_RATE, RESPONSE_CONFIDENCE


def score_text(text: str) -> float:
    """Return a naive confidence score for ``text``.

    The score is the ratio of alphabetic characters to the total length
    of the text. Empty strings yield a score of 0.0.
    """
    if not text:
        return 0.0
    alpha = sum(1 for c in text if c.isalpha())
    return alpha / len(text)


def filter_low_confidence(items: Iterable[str], threshold: float) -> List[str]:
    """Filter ``items`` removing those with a score below ``threshold``."""
    result: List[str] = []
    for item in items:
        score = score_text(item)
        RESPONSE_CONFIDENCE.observe(score)
        if score >= threshold:
            result.append(item)
        else:
            FALSE_TEXT_RATE.inc()
    return result
