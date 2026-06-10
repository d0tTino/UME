from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
from collections.abc import Iterator

import pytest


@pytest.fixture()
def vector_backend_module() -> Iterator[types.ModuleType]:
    root = Path(__file__).resolve().parents[1] / "src" / "ume"
    module_names = [
        "ume",
        "ume.capability_schema",
        "ume.config",
        "ume.plugins",
        "ume.plugins.registry",
        "ume.vector_store",
        "ume.vector_backends",
        "numpy",
        "numpy.typing",
        "prometheus_client",
    ]
    old_modules = {name: sys.modules.get(name) for name in module_names}

    class _NDArray:
        def __class_getitem__(cls, item: object) -> type[_NDArray]:
            return cls

    try:
        package = types.ModuleType("ume")
        package.__path__ = [str(root)]
        sys.modules["ume"] = package

        plugins_package = types.ModuleType("ume.plugins")
        plugins_package.__path__ = [str(root / "plugins")]
        sys.modules["ume.plugins"] = plugins_package

        numpy_stub = types.ModuleType("numpy")
        numpy_stub.float64 = float  # type: ignore[attr-defined]
        sys.modules["numpy"] = numpy_stub
        numpy_typing_stub = types.ModuleType("numpy.typing")
        numpy_typing_stub.NDArray = _NDArray  # type: ignore[attr-defined]
        sys.modules["numpy.typing"] = numpy_typing_stub

        prometheus_stub = types.ModuleType("prometheus_client")
        prometheus_stub.Gauge = object  # type: ignore[attr-defined]
        prometheus_stub.Histogram = object  # type: ignore[attr-defined]
        sys.modules["prometheus_client"] = prometheus_stub

        config_stub = types.ModuleType("ume.config")
        config_stub.settings = types.SimpleNamespace(  # type: ignore[attr-defined]
            UME_VECTOR_INDEX="vectors.faiss",
            UME_VECTOR_USE_GPU=False,
            UME_VECTOR_GPU_MEM_MB=256,
            UME_MILVUS_URI="http://localhost:19530",
            UME_MILVUS_USER=None,
            UME_MILVUS_PASSWORD=None,
        )
        sys.modules["ume.config"] = config_stub

        vector_store_stub = types.ModuleType("ume.vector_store")

        class VectorBackend:
            pass

        vector_store_stub.VectorBackend = VectorBackend  # type: ignore[attr-defined]
        sys.modules["ume.vector_store"] = vector_store_stub

        for module_name, path in [
            ("ume.capability_schema", root / "capability_schema.py"),
            ("ume.plugins.registry", root / "plugins" / "registry.py"),
            ("ume.vector_backends", root / "vector_backends" / "__init__.py"),
        ]:
            spec = importlib.util.spec_from_file_location(module_name, path)
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

        yield sys.modules["ume.vector_backends"]
    finally:
        for name, module in old_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def test_vector_entry_point_rejects_missing_capabilities(
    vector_backend_module: types.ModuleType,
) -> None:
    class MemoryBackend:
        pass

    with pytest.raises(
        vector_backend_module.VectorBackendRegistrationError,
        match=(
            "Entry point 'memory' backend 'memory' must declare capabilities.*"
            "Expected schema: mapping with 'constructor'.*'capabilities'"
        ),
    ):
        vector_backend_module._register_external_loaded_object(
            "memory",
            {"constructor": MemoryBackend},
        )


def test_vector_entry_point_accepts_valid_backend_spec(
    vector_backend_module: types.ModuleType,
) -> None:
    class MemoryBackend:
        pass

    vector_backend_module._register_external_loaded_object(
        "memory",
        {
            "constructor": MemoryBackend,
            "capabilities": {"vector_similarity", "bulk_write"},
        },
    )

    registry = sys.modules["ume.plugins.registry"]
    metadata = registry.get_plugin_metadata(
        vector_backend_module.VECTOR_BACKEND_CAPABILITY,
        "memory",
    )

    assert vector_backend_module.get_backend("memory") is MemoryBackend
    assert metadata.capabilities == frozenset({"vector_similarity", "bulk_write"})
    assert metadata.details["capability_schema"]["domain"] == "vector"
    assert metadata.details["capability_schema"]["declared"] == [
        "bulk_write",
        "vector_similarity",
    ]
