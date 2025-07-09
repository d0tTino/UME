"""HTTP client helpers for managing Rego policies via the API."""

from __future__ import annotations

import httpx


class PolicyAPI:
    """Simple wrapper for the policy management endpoints."""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.Client(timeout=5)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def save_policy(self, name: str, content: str) -> None:
        """Create a new policy file on the server."""
        files = {"file": (name, content.encode("utf-8"))}
        resp = self._client.post(f"{self.base_url}/policies/{name}", files=files, headers=self._headers())
        resp.raise_for_status()

    def edit_policy(self, name: str, content: str) -> None:
        """Replace an existing policy on the server."""
        files = {"file": (name, content.encode("utf-8"))}
        resp = self._client.put(f"{self.base_url}/policies/{name}", files=files, headers=self._headers())
        resp.raise_for_status()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PolicyAPI":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        self.close()
