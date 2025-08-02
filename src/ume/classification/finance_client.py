"""Client for the external finance-engine service."""

from __future__ import annotations

from typing import Any, List
from types import TracebackType

import httpx

from ..config import settings


class FinanceClientError(Exception):
    """Errors raised when communicating with the finance engine."""


class FinanceClient:
    """Simple HTTP wrapper around the finance-engine categorisation endpoint."""

    def __init__(self, base_url: str | None = None, timeout: float = 5.0) -> None:
        resolved = base_url or getattr(settings, "FINANCE_ENGINE_URL", "http://finance-engine:8000")
        self.base_url = str(resolved).rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def categorize(self, transaction: dict[str, Any]) -> List[str]:
        """Return a list of categories for ``transaction``."""

        url = f"{self.base_url}/categorize"
        try:
            resp = self._client.post(url, json={"transaction": transaction})
            resp.raise_for_status()
            data = resp.json()
            cats = data.get("categories")
            if isinstance(cats, list):
                return [str(c) for c in cats]
            return []
        except Exception as exc:  # pragma: no cover - network failures
            raise FinanceClientError(str(exc)) from exc

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "FinanceClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
