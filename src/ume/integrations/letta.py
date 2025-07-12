from __future__ import annotations

from ume.integrations.base import BaseClient, AsyncBaseClient


class Letta(BaseClient):
    """Thin wrapper to forward events to a running UME instance."""


class AsyncLetta(AsyncBaseClient):
    """Async wrapper to forward events to a running UME instance."""
