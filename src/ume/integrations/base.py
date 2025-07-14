from __future__ import annotations

import os
from typing import Any, Iterable, Mapping
from types import TracebackType

import httpx


class IntegrationError(Exception):
    """Raised when an HTTP request to the UME API fails."""


class BaseClient:
    """Sync client for forwarding events to a running UME instance."""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("UME_API_TOKEN")
        self._client = httpx.Client(timeout=5)

    def _auth_headers(self) -> Mapping[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def send_events(self, events: Iterable[Mapping[str, Any]]) -> None:
        headers = self._auth_headers()
        events_list = list(events)
        if not events_list:
            return
        try:
            if len(events_list) > 1:
                resp = self._client.post(
                    f"{self.base_url}/events/batch", json=events_list, headers=headers
                )
            else:
                resp = self._client.post(
                    f"{self.base_url}/events", json=events_list[0], headers=headers
                )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise IntegrationError(str(exc)) from exc

    def recall(self, payload: Mapping[str, Any]) -> Any:
        headers = self._auth_headers()
        try:
            resp = self._client.get(
                f"{self.base_url}/recall", params=payload, headers=headers
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            raise IntegrationError(str(exc)) from exc

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BaseClient":
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        self.close()


class AsyncBaseClient:
    """Async client for forwarding events to a running UME instance."""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("UME_API_TOKEN")
        self._client = httpx.AsyncClient(timeout=5)

    def _auth_headers(self) -> Mapping[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    async def send_events(self, events: Iterable[Mapping[str, Any]]) -> None:
        headers = self._auth_headers()
        events_list = list(events)
        if not events_list:
            return
        try:
            if len(events_list) > 1:
                resp = await self._client.post(
                    f"{self.base_url}/events/batch", json=events_list, headers=headers
                )
            else:
                resp = await self._client.post(
                    f"{self.base_url}/events", json=events_list[0], headers=headers
                )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise IntegrationError(str(exc)) from exc

    async def recall(self, payload: Mapping[str, Any]) -> Any:
        headers = self._auth_headers()
        try:
            resp = await self._client.get(
                f"{self.base_url}/recall", params=payload, headers=headers
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            raise IntegrationError(str(exc)) from exc

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncBaseClient":
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        await self.close()
