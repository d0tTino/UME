from __future__ import annotations

import logging
from threading import Lock
from typing import Any, Protocol, List

logger = logging.getLogger(__name__)

class WatcherHook(Protocol):
    """Callback invoked with watcher payloads."""

    def __call__(self, payload: dict[str, Any]) -> None:
        ...


_hooks: List[WatcherHook] = []
_lock = Lock()


def register_hook(hook: WatcherHook) -> None:
    """Register a watcher hook."""
    with _lock:
        _hooks.append(hook)


def unregister_hook(hook: WatcherHook) -> None:
    """Remove a previously registered hook."""
    with _lock:
        if hook in _hooks:
            _hooks.remove(hook)


def notify_hooks(payload: dict[str, Any]) -> None:
    """Call all registered hooks with ``payload``."""
    with _lock:
        hooks = list(_hooks)
    for hook in hooks:
        try:
            hook(payload)
        except Exception:  # pragma: no cover - avoid failing on hook errors
            logger.exception("Watcher hook failed")
