from __future__ import annotations

import types
import sys

import pytest

from ume.adapters import bootstrap
from ume.adapters.registry import (
    clear_graph_backend_registry,
    create_registered_graph_adapter,
    discover_graph_backends_from_entry_points,
    discover_graph_backends_from_modules,
    register_graph_backend,
    get_graph_backend_capabilities,
)
from ume.plugins.registry import clear_plugins
from ume import factories


@pytest.fixture(autouse=True)
def _reset_registry_state(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_graph_backend_registry()
    clear_plugins()
    monkeypatch.setattr(bootstrap, "_BUILTINS_REGISTERED", False)


class _Adapter:
    def __init__(self, db_path: str | None) -> None:
        self.db_path = db_path


def test_registry_default_backend_lookup() -> None:
    register_graph_backend("persistent", _Adapter, capabilities={"bulk_write"})

    adapter = create_registered_graph_adapter("unknown", "graph.db", default="persistent")

    assert isinstance(adapter, _Adapter)
    assert adapter.db_path == "graph.db"


def test_factory_can_use_runtime_registered_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    register_graph_backend("custom", _Adapter, capabilities={"bulk_write"})
    monkeypatch.setattr(factories, "register_builtin_graph_backends", lambda: None)
    monkeypatch.setattr(
        factories,
        "ensure_external_graph_backends_discovered",
        lambda module_paths=(): None,
    )
    monkeypatch.setattr(factories.settings, "UME_GRAPH_BACKEND", "custom", raising=False)
    monkeypatch.setattr(factories.settings, "UME_ROLE", None, raising=False)
    monkeypatch.setattr(factories, "is_tracing_enabled", lambda: False)

    adapter = factories.create_graph_adapter("custom.db")

    assert isinstance(adapter, _Adapter)
    assert adapter.db_path == "custom.db"


def test_discover_graph_backends_from_modules() -> None:
    module = types.ModuleType("tmp_custom_graph_module")

    def _register(register, register_lazy) -> None:  # noqa: ANN001
        del register_lazy
        register("module_custom", _Adapter, capabilities={"bulk_write"})

    module.register_graph_backends = _register  # type: ignore[attr-defined]
    sys.modules[module.__name__] = module
    try:
        discover_graph_backends_from_modules([module.__name__])
        adapter = create_registered_graph_adapter("module_custom", "from-module.db")
    finally:
        sys.modules.pop(module.__name__, None)

    assert isinstance(adapter, _Adapter)
    assert adapter.db_path == "from-module.db"


def test_discover_graph_backends_from_entry_points(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeEntryPoint:
        name = "ep_custom"

        @staticmethod
        def load():
            return _Adapter

    monkeypatch.setattr(
        "ume.plugins.registry.entry_points",
        lambda group: [_FakeEntryPoint()] if group == "ume.graph_adapters" else [],
    )

    discover_graph_backends_from_entry_points()
    adapter = create_registered_graph_adapter("ep_custom", "from-ep.db")

    assert isinstance(adapter, _Adapter)
    assert adapter.db_path == "from-ep.db"




def test_register_graph_backend_requires_capabilities() -> None:
    with pytest.raises(ValueError, match="must declare capabilities"):
        register_graph_backend("missing", _Adapter)

def test_registry_exposes_backend_capabilities() -> None:
    register_graph_backend("postgres", _Adapter, capabilities={"transactional"})

    assert get_graph_backend_capabilities("postgres") == frozenset({"transactional"})
