from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from importlib import import_module

from ume.graph_adapter import IGraphAdapter
from ume.plugins.registry import (
    ConstructorMetadata,
    PluginRegistrationError,
    clear_plugins,
    create_plugin,
    discover_plugins_from_entry_points,
    ensure_plugins_discovered,
    get_plugin_constructor,
    list_plugins,
    register_lazy_plugin,
    register_plugin,
)

GraphAdapterConstructor = Callable[[str | None], IGraphAdapter]
LazyConstructorLoader = Callable[[], GraphAdapterConstructor]

GRAPH_BACKEND_CAPABILITY = "graph_backend"
GRAPH_BACKEND_ENTRYPOINT_GROUP = "ume.graph_adapters"


class GraphAdapterRegistrationError(PluginRegistrationError):
    """Raised when graph adapter registration metadata is invalid."""


def register_graph_backend(name: str, constructor: GraphAdapterConstructor) -> None:
    """Register a graph backend constructor under ``name``."""
    register_plugin(GRAPH_BACKEND_CAPABILITY, name, constructor)


def register_lazy_graph_backend(name: str, loader: LazyConstructorLoader) -> None:
    """Register a deferred loader for backend ``name``."""
    register_lazy_plugin(
        GRAPH_BACKEND_CAPABILITY,
        name,
        loader,
        metadata=ConstructorMetadata(lazy=True),
    )


def get_graph_backend_constructor(
    name: str,
    *,
    default: str | None = None,
) -> GraphAdapterConstructor:
    """Return constructor for ``name``, resolving lazy registrations on demand."""
    return get_plugin_constructor(
        GRAPH_BACKEND_CAPABILITY,
        name,
        default=default,
    )


def create_registered_graph_adapter(
    name: str,
    db_path: str | None,
    *,
    default: str | None = None,
) -> IGraphAdapter:
    """Instantiate backend ``name`` using the registration table."""
    return create_plugin(
        GRAPH_BACKEND_CAPABILITY,
        name,
        db_path,
        default=default,
    )


def available_graph_backends() -> list[str]:
    """Return all known graph backend keys."""
    return [
        item["name"]
        for item in list_plugins(capability=GRAPH_BACKEND_CAPABILITY)
    ]


def clear_graph_backend_registry() -> None:
    """Reset all registered and lazy graph backend constructors."""
    clear_plugins(capability=GRAPH_BACKEND_CAPABILITY)


def _register_external_loaded_object(name: str, loaded: object) -> None:
    if callable(loaded):
        register_graph_backend(name, loaded)
        return
    if isinstance(loaded, Mapping):
        for backend_name, constructor in loaded.items():
            if not callable(constructor):
                raise GraphAdapterRegistrationError(
                    f"Constructor for backend '{backend_name}' is not callable"
                )
            register_graph_backend(str(backend_name), constructor)
        return
    raise GraphAdapterRegistrationError(
        f"Entry point '{name}' must load a constructor or backend mapping"
    )


def discover_graph_backends_from_entry_points(
    *,
    group: str = GRAPH_BACKEND_ENTRYPOINT_GROUP,
) -> None:
    """Load external graph backend registrations from Python entry points."""
    discover_plugins_from_entry_points(
        capability=GRAPH_BACKEND_CAPABILITY,
        group=group,
        loader=_register_external_loaded_object,
    )


def discover_graph_backends_from_modules(module_paths: Iterable[str]) -> None:
    """Load graph backend registrations from importable module paths."""
    for module_path in module_paths:
        module_name = module_path.strip()
        if not module_name:
            continue
        module = import_module(module_name)
        registration_hook = getattr(module, "register_graph_backends", None)
        if callable(registration_hook):
            registration_hook(register_graph_backend, register_lazy_graph_backend)
            continue
        adapter_map = getattr(module, "GRAPH_ADAPTERS", None)
        if isinstance(adapter_map, Mapping):
            _register_external_loaded_object(module_name, adapter_map)
            continue
        raise GraphAdapterRegistrationError(
            f"Module '{module_name}' must define register_graph_backends or GRAPH_ADAPTERS"
        )


def discover_external_graph_backends(*, module_paths: Iterable[str] = ()) -> None:
    """Discover graph backends via entry points and optional module paths."""
    discover_graph_backends_from_entry_points()
    discover_graph_backends_from_modules(module_paths)


def ensure_external_graph_backends_discovered(*, module_paths: Iterable[str] = ()) -> None:
    """Run external discovery once per process."""
    ensure_plugins_discovered(
        capability=GRAPH_BACKEND_CAPABILITY,
        group=GRAPH_BACKEND_ENTRYPOINT_GROUP,
        discover=lambda: discover_external_graph_backends(module_paths=module_paths),
    )
