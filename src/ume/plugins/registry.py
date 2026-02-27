from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from threading import Lock
from typing import Any


class PluginRegistrationError(ValueError):
    """Raised when plugin registration metadata is invalid."""


@dataclass(frozen=True)
class ConstructorMetadata:
    """Metadata describing how a plugin constructor was registered."""

    source: str = "runtime"
    entry_point_group: str | None = None
    module_path: str | None = None
    lazy: bool = False
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _RegisteredPlugin:
    capability: str
    name: str
    constructor: Callable[..., Any]
    metadata: ConstructorMetadata


_PLUGIN_CONSTRUCTORS: dict[str, dict[str, Callable[..., Any]]] = {}
_LAZY_PLUGINS: dict[str, dict[str, Callable[[], Callable[..., Any]]]] = {}
_PLUGIN_METADATA: dict[str, dict[str, ConstructorMetadata]] = {}
_DISCOVERED_GROUPS: set[tuple[str, str]] = set()
_DISCOVERY_LOCK = Lock()


def register_plugin(
    capability: str,
    name: str,
    constructor: Callable[..., Any],
    *,
    metadata: ConstructorMetadata | None = None,
) -> None:
    """Register a constructor under ``capability`` and ``name``."""
    capability_key = capability.lower()
    name_key = name.lower()
    _PLUGIN_CONSTRUCTORS.setdefault(capability_key, {})[name_key] = constructor
    _PLUGIN_METADATA.setdefault(capability_key, {})[name_key] = (
        metadata or ConstructorMetadata()
    )


def register_lazy_plugin(
    capability: str,
    name: str,
    loader: Callable[[], Callable[..., Any]],
    *,
    metadata: ConstructorMetadata | None = None,
) -> None:
    """Register a lazy constructor loader under ``capability`` and ``name``."""
    capability_key = capability.lower()
    name_key = name.lower()
    _LAZY_PLUGINS.setdefault(capability_key, {})[name_key] = loader
    _PLUGIN_METADATA.setdefault(capability_key, {})[name_key] = (
        metadata or ConstructorMetadata(lazy=True)
    )


def get_plugin_constructor(
    capability: str,
    name: str,
    *,
    default: str | None = None,
) -> Callable[..., Any]:
    """Return a constructor for ``name``, resolving lazy entries on demand."""
    capability_key = capability.lower()
    key = name.lower()
    constructors = _PLUGIN_CONSTRUCTORS.setdefault(capability_key, {})
    lazy = _LAZY_PLUGINS.setdefault(capability_key, {})

    constructor = constructors.get(key)
    if constructor is None and key in lazy:
        constructor = lazy.pop(key)()
        constructors[key] = constructor
        current = _PLUGIN_METADATA.setdefault(capability_key, {}).get(key)
        if current is not None:
            _PLUGIN_METADATA[capability_key][key] = ConstructorMetadata(
                source=current.source,
                entry_point_group=current.entry_point_group,
                module_path=current.module_path,
                lazy=False,
                details=current.details,
            )
    if constructor is not None:
        return constructor
    if default is not None and default.lower() != key:
        return get_plugin_constructor(capability, default)
    raise ValueError(f"Unknown {capability} plugin: {name}")


def create_plugin(
    capability: str,
    name: str,
    *args: Any,
    default: str | None = None,
    **kwargs: Any,
) -> Any:
    """Instantiate a registered plugin using ``*args`` and ``**kwargs``."""
    constructor = get_plugin_constructor(capability, name, default=default)
    return constructor(*args, **kwargs)


def list_plugins(*, capability: str | None = None) -> list[dict[str, Any]]:
    """List plugin names and constructor metadata."""
    capabilities = [capability.lower()] if capability else sorted(_PLUGIN_METADATA)
    listed: list[dict[str, Any]] = []
    for capability_key in capabilities:
        names = set(_PLUGIN_CONSTRUCTORS.get(capability_key, {})) | set(
            _LAZY_PLUGINS.get(capability_key, {})
        )
        for name in sorted(names):
            metadata = _PLUGIN_METADATA.get(capability_key, {}).get(name)
            listed.append(
                {
                    "capability": capability_key,
                    "name": name,
                    "metadata": metadata or ConstructorMetadata(),
                }
            )
    return listed


def clear_plugins(*, capability: str | None = None) -> None:
    """Clear all plugin registrations or only those for one capability."""
    if capability is None:
        _PLUGIN_CONSTRUCTORS.clear()
        _LAZY_PLUGINS.clear()
        _PLUGIN_METADATA.clear()
        _DISCOVERED_GROUPS.clear()
        return
    capability_key = capability.lower()
    _PLUGIN_CONSTRUCTORS.pop(capability_key, None)
    _LAZY_PLUGINS.pop(capability_key, None)
    _PLUGIN_METADATA.pop(capability_key, None)
    _DISCOVERED_GROUPS.difference_update(
        {item for item in _DISCOVERED_GROUPS if item[0] == capability_key}
    )


def discover_plugins_from_entry_points(
    *,
    capability: str,
    group: str,
    loader: Callable[[str, object], None] | None = None,
) -> None:
    """Discover plugins from the Python ``entry_points`` API."""
    for ep in entry_points(group=group):
        loaded = ep.load()
        if loader is None:
            if not callable(loaded):
                raise PluginRegistrationError(
                    f"Entry point '{ep.name}' must load a callable constructor"
                )
            register_plugin(
                capability,
                ep.name,
                loaded,
                metadata=ConstructorMetadata(source="entry_point", entry_point_group=group),
            )
            continue
        loader(ep.name, loaded)


def ensure_plugins_discovered(
    *,
    capability: str,
    group: str,
    discover: Callable[[], None],
) -> None:
    """Run discovery once per process for ``(capability, group)``."""
    key = (capability.lower(), group)
    if key in _DISCOVERED_GROUPS:
        return
    with _DISCOVERY_LOCK:
        if key in _DISCOVERED_GROUPS:
            return
        discover()
        _DISCOVERED_GROUPS.add(key)

