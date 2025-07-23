from __future__ import annotations

import os

from ume.integrations.base import BaseClient, AsyncBaseClient


class LangGraph(BaseClient):
    """Thin wrapper to forward events to a running UME instance."""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str | None = None) -> None:
        super().__init__(base_url, api_key or os.getenv("LANGGRAPH_UME_API_TOKEN"))


class AsyncLangGraph(AsyncBaseClient):
    """Async wrapper to forward events to a running UME instance."""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str | None = None) -> None:
        super().__init__(base_url, api_key or os.getenv("LANGGRAPH_UME_API_TOKEN"))

