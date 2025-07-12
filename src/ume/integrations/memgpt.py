from __future__ import annotations

from ume.integrations.base import BaseClient, AsyncBaseClient


class MemGPT(BaseClient):
    """Thin wrapper to forward events to a running UME instance."""


class AsyncMemGPT(AsyncBaseClient):
    """Async wrapper to forward events to a running UME instance."""
