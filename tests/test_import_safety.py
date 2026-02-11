"""Import-safety checks for the top-level ``ume`` package."""

from __future__ import annotations

import builtins
import importlib
import sys

import pytest


_OPTIONAL_MODULE_PREFIXES = (
    "faiss",
    "sentence_transformers",
    "chromadb",
    "pymilvus",
)


def _without_optional_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def guarded_import(name: str, *args: object, **kwargs: object):
        if name.startswith(_OPTIONAL_MODULE_PREFIXES):
            raise ImportError(f"blocked optional dependency: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)


def test_importing_ume_is_safe_without_optional_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _without_optional_imports(monkeypatch)
    for mod_name in list(sys.modules):
        if mod_name == "ume" or mod_name.startswith("ume."):
            sys.modules.pop(mod_name, None)

    ume = importlib.import_module("ume")

    assert ume.Event is not None
    assert "ume.vector_store" not in sys.modules
    assert "ume.neo4j_graph" not in sys.modules


def test_compat_runtime_exports_emit_deprecation_warning() -> None:
    import ume

    with pytest.warns(DeprecationWarning):
        vector_store_type = ume.VectorStore

    assert vector_store_type is not None
