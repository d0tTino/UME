from __future__ import annotations

from ume.integrations.base import BaseClient, AsyncBaseClient


class SuperMemory(BaseClient):
    """Thin wrapper to forward events to a running UME instance."""


class AsyncSuperMemory(AsyncBaseClient):
    """Async wrapper to forward events to a running UME instance."""
