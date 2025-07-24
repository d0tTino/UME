"""Filesystem and configuration change watchers."""

import os

from .hooks import register_hook, unregister_hook, WatcherHook, notify_hooks
from .dossier_hook import dossier_activity_hook

# Automatically record watcher activity in the user's dossier when enabled
if os.getenv("UME_ACTIVITY_LOG_ENABLED", "true").lower() not in {"0", "false", "no"}:
    register_hook(dossier_activity_hook)

__all__ = [
    "register_hook",
    "unregister_hook",
    "notify_hooks",
    "WatcherHook",
]

