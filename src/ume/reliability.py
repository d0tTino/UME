from __future__ import annotations

from typing import Iterable, List

from langdetect import LangDetectException, detect_langs

from .metrics import FALSE_TEXT_RATE, RESPONSE_CONFIDENCE


def score_text(text: str) -> float:
    """Return a confidence score for ``text`` using language detection."""
    if not text:
        return 0.0

    alpha_ratio = sum(1 for c in text if c.isalpha()) / len(text)

    try:
        detection = detect_langs(text)
        prob = detection[0].prob if detection else 0.0
    except LangDetectException:
        prob = 0.0

    return alpha_ratio * prob


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
