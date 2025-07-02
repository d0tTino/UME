from __future__ import annotations

from typing import Iterable, Mapping, Any

import httpx


class Letta:
    """Thin wrapper to forward events to a running UME instance."""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.Client(timeout=5)

    def send_events(self, events: Iterable[Mapping[str, Any]]) -> None:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        self._client.post(f"{self.base_url}/events", json=list(events), headers=headers)

    def recall(self, payload: Mapping[str, Any]) -> Any:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        resp = self._client.post(f"{self.base_url}/recall", json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "Letta":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
