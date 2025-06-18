from __future__ import annotations

from typing import Dict, Any
import logging

import httpx

from .config import settings
from ._internal.listeners import GraphListener

logger = logging.getLogger(__name__)


class LLMFerry(GraphListener):
    """GraphListener that forwards events to an external service."""

    def __init__(self, api_url: str | None = None, api_key: str | None = None) -> None:
        self.api_url = api_url or settings.LLM_FERRY_API_URL
        self.api_key = api_key or settings.LLM_FERRY_API_KEY

    def _send(self, text: str) -> None:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            httpx.post(self.api_url, json={"text": text}, headers=headers, timeout=5)
        except Exception:  # pragma: no cover - network errors are logged
            logger.exception("Failed to send event")

    def on_node_created(self, node_id: str, attributes: Dict[str, Any]) -> None:
        self._send(f"Node created: {node_id} {attributes}")

    def on_node_updated(self, node_id: str, attributes: Dict[str, Any]) -> None:
        self._send(f"Node updated: {node_id} {attributes}")

    def on_edge_created(self, source_node_id: str, target_node_id: str, label: str) -> None:
        self._send(f"Edge created: {source_node_id} -[{label}]-> {target_node_id}")

    def on_edge_deleted(self, source_node_id: str, target_node_id: str, label: str) -> None:
        self._send(f"Edge deleted: {source_node_id} -[{label}]-> {target_node_id}")
