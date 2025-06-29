from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .config import settings

if TYPE_CHECKING:  # pragma: no cover - for type hints only
    from .agent_orchestrator import AgentTask
    from .message_bus import MessageEnvelope


class ValueOverseer:
    """Check tasks against a stored list of disallowed actions."""

    def __init__(self, store_path: str | None = None) -> None:
        self.store_path = store_path or settings.UME_VALUE_STORE_PATH
        self._blocked = self._load_blocked()

    def _load_blocked(self) -> list[str]:
        if not self.store_path:
            return []
        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return []
        if isinstance(data, dict):
            data = data.get("blocked", [])
        if not isinstance(data, list):
            return []
        return [str(item) for item in data]

    def reload(self) -> None:
        """Reload the block list from disk."""
        self._blocked = self._load_blocked()

    def is_allowed(self, task: AgentTask) -> bool:
        """Return ``True`` if the task is permitted."""
        for forbidden in self._blocked:
            if forbidden in task.payload:
                return False
        return True

    def hallucination_check(
        self,
        message: MessageEnvelope,
        *,
        task: AgentTask | None = None,
        agent_id: str | None = None,
    ) -> MessageEnvelope:  # pragma: no cover - default passthrough
        return message
