from __future__ import annotations

from typing import Iterable, Mapping, Any
from types import TracebackType

import httpx


class MemGPT:
    """Thin wrapper to forward events to a running UME instance."""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.Client(timeout=5)

    def send_events(self, events: Iterable[Mapping[str, Any]]) -> None:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        events_list = list(events)
        if not events_list:
            return
        if len(events_list) > 1:
            self._client.post(
                f"{self.base_url}/events/batch", json=events_list, headers=headers
            )
        else:
            self._client.post(
                f"{self.base_url}/events", json=events_list[0], headers=headers
            )

    def recall(self, payload: Mapping[str, Any]) -> Any:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        resp = self._client.get(
            f"{self.base_url}/recall", params=payload, headers=headers
        )
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MemGPT":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
