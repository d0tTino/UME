from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from importlib import import_module
from importlib.metadata import entry_points
from threading import Lock

from ume.graph_adapter import IGraphAdapter

GraphAdapterConstructor = Callable[[str | None], IGraphAdapter]
LazyConstructorLoader = Callable[[], GraphAdapterConstructor]

_BACKEND_CONSTRUCTORS: dict[str, GraphAdapterConstructor] = {}
_LAZY_BACKENDS: dict[str, LazyConstructorLoader] = {}
_DISCOVERY_LOCK = Lock()
_EXTERNAL_DISCOVERED = False


class GraphAdapterRegistrationError(ValueError):
    """Raised when adapter registration metadata is invalid."""


def register_graph_backend(name: str, constructor: GraphAdapterConstructor) -> None:
    """Register a graph backend constructor under ``name``."""
    _BACKEND_CONSTRUCTORS[name.lower()] = constructor


def register_lazy_graph_backend(name: str, loader: LazyConstructorLoader) -> None:
    """Register a deferred loader for backend ``name``."""
    _LAZY_BACKENDS[name.lower()] = loader


def get_graph_backend_constructor(
    name: str,
    *,
    default: str | None = None,
) -> GraphAdapterConstructor:
    """Return constructor for ``name``, resolving lazy registrations on demand."""
    key = name.lower()
    constructor = _BACKEND_CONSTRUCTORS.get(key)
    if constructor is None and key in _LAZY_BACKENDS:
        constructor = _LAZY_BACKENDS.pop(key)()
        _BACKEND_CONSTRUCTORS[key] = constructor
    if constructor is not None:
        return constructor
    if default is not None and default.lower() != key:
        return get_graph_backend_constructor(default)
    raise ValueError(f"Unknown graph backend: {name}")


def create_registered_graph_adapter(
    name: str,
    db_path: str | None,
    *,
    default: str | None = None,
) -> IGraphAdapter:
    """Instantiate backend ``name`` using the registration table."""
    constructor = get_graph_backend_constructor(name, default=default)
    return constructor(db_path)


def available_graph_backends() -> list[str]:
    """Return all known graph backend keys."""
    return sorted(set(_BACKEND_CONSTRUCTORS) | set(_LAZY_BACKENDS))


def clear_graph_backend_registry() -> None:
    """Reset all registered and lazy graph backend constructors."""
    _BACKEND_CONSTRUCTORS.clear()
    _LAZY_BACKENDS.clear()


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
    group: str = "ume.graph_adapters",
) -> None:
    """Load external graph backend registrations from Python entry points."""
    for ep in entry_points(group=group):
        _register_external_loaded_object(ep.name, ep.load())


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
    global _EXTERNAL_DISCOVERED
    if _EXTERNAL_DISCOVERED:
        return
    with _DISCOVERY_LOCK:
        if _EXTERNAL_DISCOVERED:
            return
        discover_external_graph_backends(module_paths=module_paths)
        _EXTERNAL_DISCOVERED = True
