"""Classifier integration for the tino-storm service or a local NLP model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, TYPE_CHECKING

import httpx

from ..config import settings

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .service import TagResult


class TinoStormError(Exception):
    """Errors raised when communicating with tino-storm."""


@dataclass
class _LocalRule:
    keyword: str
    domain: str
    subdomain: str
    sensitivity: str


class TinoStormClassifier:
    """Classifier calling tino-storm remotely or a simple local NLP model."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        local_model: Optional[str] = None,
    ) -> None:
        self.base_url = (base_url or getattr(settings, "TINO_STORM_URL", None))
        self.local_model = local_model or getattr(settings, "TINO_STORM_LOCAL_MODEL", None)
        if self.base_url:
            self.base_url = self.base_url.rstrip("/")
            self._client: Optional[httpx.Client] = httpx.Client(timeout=5.0)
        else:
            self._client = None
        # Very small rule-based model for local classification
        self._rules = [
            _LocalRule("password", "credentials", "password", "high"),
            _LocalRule("email", "contact", "email", "medium"),
        ]

    def classify(self, payload: dict[str, Any]) -> List["TagResult"]:
        text = self._extract_text(payload)
        if not text:
            return []

        if self._client and self.base_url:
            url = f"{self.base_url}/classify"
            try:
                from .service import TagResult

                resp = self._client.post(url, json={"text": text})
                resp.raise_for_status()
                data = resp.json()
                domain = data.get("domain")
                subdomain = data.get("subdomain")
                sensitivity = data.get("sensitivity")
                confidence = float(data.get("confidence", 1.0))
                if domain and subdomain and sensitivity:
                    tag = f"{domain}:{subdomain}:{sensitivity}"
                    return [
                        TagResult(
                            tag=tag,
                            confidence=confidence,
                            domain=domain,
                            subdomain=subdomain,
                            sensitivity=sensitivity,
                        )
                    ]
                return []
            except Exception as exc:  # pragma: no cover - network errors
                raise TinoStormError(str(exc)) from exc

        # Local rule-based classification
        from .service import TagResult

        lower = text.lower()
        for rule in self._rules:
            if rule.keyword in lower:
                tag = f"{rule.domain}:{rule.subdomain}:{rule.sensitivity}"
                return [
                    TagResult(
                        tag=tag,
                        confidence=1.0,
                        domain=rule.domain,
                        subdomain=rule.subdomain,
                        sensitivity=rule.sensitivity,
                    )
                ]
        return []

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str | None:
        for key, value in payload.items():
            if key == "node_id":
                continue
            if isinstance(value, str):
                return value
        attrs = payload.get("attributes")
        if isinstance(attrs, dict):
            for value in attrs.values():
                if isinstance(value, str):
                    return value
        return None
