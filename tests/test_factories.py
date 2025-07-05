import importlib.util
from pathlib import Path
import sys
import types
import os

import pytest

root = Path(__file__).resolve().parents[1] / "src" / "ume"
os.environ.setdefault("UME_AUDIT_SIGNING_KEY", "test-key")
old_ume = sys.modules.get("ume")
package = types.ModuleType("ume")
package.__path__ = [str(root)]
sys.modules["ume"] = package
old_alignment = sys.modules.get("ume.plugins.alignment")
old_vector_store = sys.modules.get("ume.vector_store")
old_tracing = sys.modules.get("ume.tracing")

spec = importlib.util.spec_from_file_location("ume.rbac_adapter", root / "rbac_adapter.py")
assert spec and spec.loader
rbac_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rbac_module
spec.loader.exec_module(rbac_module)
RoleBasedGraphAdapter = rbac_module.RoleBasedGraphAdapter

spec = importlib.util.spec_from_file_location("ume.factories", root / "factories.py")
assert spec and spec.loader
factories = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = factories
# Stub out optional alignment plugins to avoid importing extra dependencies
plugin_stub = types.ModuleType("ume.plugins.alignment")
plugin_stub.get_plugins = lambda: []  # type: ignore[attr-defined]
sys.modules["ume.plugins.alignment"] = plugin_stub
vector_stub = types.ModuleType("ume.vector_store")
class _DummyVS:
    pass

vector_stub.VectorBackend = _DummyVS  # type: ignore[attr-defined]
vector_stub.FaissBackend = _DummyVS  # type: ignore[attr-defined]
vector_stub.VectorStore = _DummyVS  # type: ignore[attr-defined]
def _create_vs() -> _DummyVS:
    return _DummyVS()
vector_stub.create_vector_store = _create_vs  # type: ignore[attr-defined]
sys.modules["ume.vector_store"] = vector_stub
tracing_stub = types.ModuleType("ume.tracing")
class _DummyTracing:
    def __init__(self, adapter: object) -> None:
        self.adapter = adapter

tracing_stub.TracingGraphAdapter = _DummyTracing  # type: ignore[attr-defined]
tracing_stub.is_tracing_enabled = lambda: False  # type: ignore[attr-defined]
sys.modules["ume.tracing"] = tracing_stub
spec.loader.exec_module(factories)

if old_alignment is not None:
    sys.modules["ume.plugins.alignment"] = old_alignment
else:
    sys.modules.pop("ume.plugins.alignment", None)
if old_vector_store is not None:
    sys.modules["ume.vector_store"] = old_vector_store
else:
    sys.modules.pop("ume.vector_store", None)
if old_tracing is not None:
    sys.modules["ume.tracing"] = old_tracing
else:
    sys.modules.pop("ume.tracing", None)

if old_ume is not None:
    sys.modules["ume"] = old_ume
else:
    sys.modules.pop("ume", None)


class DummyGraph:
    pass


class DummyTracing:
    def __init__(self, adapter: object) -> None:
        self.adapter = adapter

def test_create_graph_adapter_with_role_and_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, object] = {}

    def dummy_persistent(path: str) -> DummyGraph:
        created["path"] = path
        return DummyGraph()

    monkeypatch.setattr(factories, "PersistentGraph", dummy_persistent)
    monkeypatch.setattr(factories, "TracingGraphAdapter", DummyTracing)
    monkeypatch.setattr(factories, "is_tracing_enabled", lambda: True)

    adapter = factories.create_graph_adapter("/tmp/test.db", role="AnalyticsAgent")

    assert isinstance(adapter, RoleBasedGraphAdapter)
    assert adapter.role == "AnalyticsAgent"
    assert isinstance(adapter._adapter, DummyTracing)
    assert isinstance(adapter._adapter.adapter, DummyGraph)
    assert created["path"] == "/tmp/test.db"

def test_memory_factories_use_configured_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(factories.settings, "UME_DB_PATH", "configured.db", raising=False)

    class DummyEpisodic:
        def __init__(self, db_path: str, log_path: str | None = None) -> None:
            self.db_path = db_path
            self.log_path = log_path

    class DummySemantic:
        def __init__(self, db_path: str) -> None:
            self.db_path = db_path

    monkeypatch.setattr(factories, "EpisodicMemory", DummyEpisodic)
    monkeypatch.setattr(factories, "SemanticMemory", DummySemantic)

    epi = factories.create_episodic_memory()
    sem = factories.create_semantic_memory()

    assert isinstance(epi, DummyEpisodic)
    assert isinstance(sem, DummySemantic)
    assert epi.db_path == "configured.db"
    assert sem.db_path == "configured.db"

def test_create_vector_store_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {}

    class DummyStore:
        pass

    def dummy_factory() -> DummyStore:
        called["made"] = True
        return DummyStore()

    monkeypatch.setattr(factories, "_create_vector_store", dummy_factory)

    store = factories.create_vector_store()
    assert isinstance(store, DummyStore)
    assert called.get("made") is True

