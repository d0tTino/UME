from __future__ import annotations

from ume.integrations.base import BaseClient, AsyncBaseClient


class AutoGen(BaseClient):
    """Thin wrapper to forward events to a running UME instance."""


class AsyncAutoGen(AsyncBaseClient):
    """Async wrapper to forward events to a running UME instance."""
