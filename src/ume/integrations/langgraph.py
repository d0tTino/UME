from __future__ import annotations

from ume.integrations.base import BaseClient, AsyncBaseClient


class LangGraph(BaseClient):
    """Thin wrapper to forward events to a running UME instance."""


class AsyncLangGraph(AsyncBaseClient):
    """Async wrapper to forward events to a running UME instance."""
