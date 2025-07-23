"""Filesystem and configuration change watchers."""

from .hooks import register_hook, unregister_hook, WatcherHook, notify_hooks
from .dossier_hook import dossier_activity_hook

# Automatically record watcher activity in the user's dossier
register_hook(dossier_activity_hook)

__all__ = [
    "register_hook",
    "unregister_hook",
    "notify_hooks",
    "WatcherHook",
]

