from __future__ import annotations

import os

from ume.integrations.base import BaseClient, AsyncBaseClient


class SuperMemory(BaseClient):
    """Thin wrapper to forward events to a running UME instance."""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str | None = None) -> None:
        super().__init__(base_url, api_key or os.getenv("SUPERMEMORY_UME_API_TOKEN"))


class AsyncSuperMemory(AsyncBaseClient):
    """Async wrapper to forward events to a running UME instance."""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str | None = None) -> None:
        super().__init__(base_url, api_key or os.getenv("SUPERMEMORY_UME_API_TOKEN"))

