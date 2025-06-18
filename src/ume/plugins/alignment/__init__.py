"""Alignment plugin interface and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Callable, cast
import importlib
import pkgutil

from ...event import Event
from ...audit import log_audit_entry
from ...config import settings


class PolicyViolationError(ValueError):
    """Raised when an event violates an alignment policy."""


class AlignmentPlugin(ABC):
    """Base class for alignment plugins."""

    @abstractmethod
    def validate(self, event: Event) -> None:
        """Validate an event.

        Implementations should raise :class:`PolicyViolationError` if the event
        violates the plugin's policy.
        """


_plugins: List[AlignmentPlugin] = []


def register_plugin(plugin: AlignmentPlugin) -> None:
    """Register a plugin instance.

    The plugin's ``validate`` method is wrapped so that any
    :class:`PolicyViolationError` raised will trigger an audit log entry.
    """

    original_validate = plugin.validate

    def wrapped_validate(event: Event) -> None:
        try:
            original_validate(event)
        except PolicyViolationError as exc:
            user_id = settings.UME_AGENT_ID
            log_audit_entry(user_id, str(exc))
            raise

    setattr(plugin, "validate", cast(Callable[[Event], None], wrapped_validate))
    _plugins.append(plugin)


def get_plugins() -> List[AlignmentPlugin]:
    """Return all registered plugins."""
    return list(_plugins)


def load_plugins() -> None:
    """Import all modules in this package so they can register plugins."""
    package = __name__
    for _, modname, _ in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{package}.{modname}")


# Load plugins on import
load_plugins()
