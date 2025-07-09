from __future__ import annotations

from typing import Mapping

try:  # optional dependency
    import httpx
except Exception:  # pragma: no cover - optional dependency missing
    httpx = None  # type: ignore

from types import TracebackType

from ..config import settings


class OPAClientError(Exception):
    """Errors raised when communicating with the OPA server."""


class OPAClient:
    """Simple wrapper around the OPA HTTP API."""

    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        if httpx is None:
            raise ImportError("httpx is required for OPAClient")
        resolved_url = base_url or settings.OPA_URL
        if not resolved_url:
            raise ValueError("OPA base URL must be provided")
        self.base_url = resolved_url
        self.token = token or settings.OPA_TOKEN
        self._client = httpx.Client(timeout=5)

    def query(self, path: str, input_data: Mapping[str, object]) -> object:
        """Execute a policy query and return the result field."""
        url = f"{self.base_url.rstrip('/')}/v1/data/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            resp = self._client.post(url, json={"input": input_data}, headers=headers)
            resp.raise_for_status()
        except Exception as exc:  # pragma: no cover - network errors
            raise OPAClientError(f"OPA request failed: {exc}") from exc
        return resp.json().get("result")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "OPAClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
