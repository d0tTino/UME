from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Set as AbstractSet
from importlib import import_module
from typing import NotRequired, TypedDict, cast

from ume.kernel.graph_adapter import IGraphAdapter
from ume.plugins.registry import (
    ConstructorMetadata,
    PluginRegistrationError,
    clear_plugins,
    create_plugin,
    discover_plugins_from_entry_points,
    ensure_plugins_discovered,
    get_plugin_constructor,
    get_plugin_metadata,
    list_plugins,
    register_lazy_plugin,
    register_plugin,
)
from ume.capability_schema import build_capability_schema

GraphAdapterConstructor = Callable[[str | None], IGraphAdapter]
LazyConstructorLoader = Callable[[], GraphAdapterConstructor]

GRAPH_BACKEND_CAPABILITY = "graph_backend"
GRAPH_BACKEND_ENTRYPOINT_GROUP = "ume.graph_adapters"


class ExternalGraphBackendSpec(TypedDict):
    """Strict shape for externally discovered graph backend registrations."""

    constructor: GraphAdapterConstructor
    capabilities: AbstractSet[str]
    name: NotRequired[str]


class GraphAdapterRegistrationError(PluginRegistrationError):
    """Raised when graph adapter registration metadata is invalid."""


def register_graph_backend(
    name: str,
    constructor: GraphAdapterConstructor,
    *,
    capabilities: set[str] | frozenset[str] | None = None,
) -> None:
    """Register a graph backend constructor under ``name``."""
    if capabilities is None:
        raise GraphAdapterRegistrationError(
            f"Graph backend '{name}' must declare capabilities"
        )
    declared = frozenset(capabilities)
    register_plugin(
        GRAPH_BACKEND_CAPABILITY,
        name,
        constructor,
        metadata=ConstructorMetadata(
            capabilities=declared,
            details={
                "capability_schema": build_capability_schema(
                    domain="graph",
                    backend=name,
                    declared=declared,
                ).as_dict()
            },
        ),
    )


def register_lazy_graph_backend(
    name: str,
    loader: LazyConstructorLoader,
    *,
    capabilities: set[str] | frozenset[str] | None = None,
) -> None:
    """Register a deferred loader for backend ``name``."""
    if capabilities is None:
        raise GraphAdapterRegistrationError(
            f"Graph backend '{name}' must declare capabilities"
        )
    declared = frozenset(capabilities)
    register_lazy_plugin(
        GRAPH_BACKEND_CAPABILITY,
        name,
        loader,
        metadata=ConstructorMetadata(
            lazy=True,
            capabilities=declared,
            details={
                "capability_schema": build_capability_schema(
                    domain="graph",
                    backend=name,
                    declared=declared,
                ).as_dict()
            },
        ),
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
    return cast(
        IGraphAdapter,
        create_plugin(
            GRAPH_BACKEND_CAPABILITY,
            name,
            db_path,
            default=default,
        ),
    )


def get_graph_backend_capabilities(name: str) -> frozenset[str]:
    """Return declared capabilities for backend ``name``."""
    metadata = get_plugin_metadata(GRAPH_BACKEND_CAPABILITY, name)
    return metadata.capabilities


def available_graph_backends() -> list[str]:
    """Return all known graph backend keys."""
    return [item["name"] for item in list_plugins(capability=GRAPH_BACKEND_CAPABILITY)]


def clear_graph_backend_registry() -> None:
    """Reset all registered and lazy graph backend constructors."""
    clear_plugins(capability=GRAPH_BACKEND_CAPABILITY)


def _parse_external_backend_spec(
    entry_name: str,
    backend_name: str,
    spec: object,
) -> tuple[str, GraphAdapterConstructor, AbstractSet[str]]:
    if not isinstance(spec, Mapping):
        raise GraphAdapterRegistrationError(
            f"Entry point '{entry_name}' backend '{backend_name}' must provide a mapping "
            "with constructor and capabilities"
        )

    constructor = spec.get("constructor")
    if not callable(constructor):
        raise GraphAdapterRegistrationError(
            f"Entry point '{entry_name}' backend '{backend_name}' must declare a callable constructor"
        )

    capabilities = spec.get("capabilities")
    if capabilities is None:
        raise GraphAdapterRegistrationError(
            f"Entry point '{entry_name}' backend '{backend_name}' must declare capabilities"
        )
    if not isinstance(capabilities, AbstractSet):
        raise GraphAdapterRegistrationError(
            f"Entry point '{entry_name}' backend '{backend_name}' capabilities must be a set-like collection"
        )

    resolved_name = spec.get("name")
    if resolved_name is not None and not isinstance(resolved_name, str):
        raise GraphAdapterRegistrationError(
            f"Entry point '{entry_name}' backend '{backend_name}' name override must be a string"
        )

    return (
        resolved_name or backend_name,
        cast(GraphAdapterConstructor, constructor),
        capabilities,
    )


def _register_external_loaded_object(name: str, loaded: object) -> None:
    if isinstance(loaded, Mapping):
        if "constructor" in loaded or "capabilities" in loaded:
            backend_name, constructor, capabilities = _parse_external_backend_spec(
                name,
                name,
                loaded,
            )
            register_graph_backend(
                backend_name, constructor, capabilities=set(capabilities)
            )
            return

        for backend_name, spec in loaded.items():
            resolved_name, constructor, capabilities = _parse_external_backend_spec(
                name,
                str(backend_name),
                spec,
            )
            register_graph_backend(
                resolved_name,
                constructor,
                capabilities=set(capabilities),
            )
        return
    raise GraphAdapterRegistrationError(
        f"Entry point '{name}' must load a backend spec or backend-spec mapping"
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


def ensure_external_graph_backends_discovered(
    *, module_paths: Iterable[str] = ()
) -> None:
    """Run external discovery once per process."""
    ensure_plugins_discovered(
        capability=GRAPH_BACKEND_CAPABILITY,
        group=GRAPH_BACKEND_ENTRYPOINT_GROUP,
        discover=lambda: discover_external_graph_backends(module_paths=module_paths),
    )
