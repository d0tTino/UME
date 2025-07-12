from __future__ import annotations

from ume.integrations.base import BaseClient, AsyncBaseClient


class CrewAI(BaseClient):
    """Thin wrapper to forward events to a running UME instance."""


class AsyncCrewAI(AsyncBaseClient):
    """Async wrapper to forward events to a running UME instance."""
