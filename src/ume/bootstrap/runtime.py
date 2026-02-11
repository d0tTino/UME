"""Runtime bootstrap helpers for optional UME integrations."""

from __future__ import annotations

import sys
from importlib import import_module
from typing import Any

from .config import load_config
from .embedding import load_embedding
from .neo4j import load_neo4j
from .vector import load_vector_modules

__all__ = ["bootstrap_runtime"]


def bootstrap_runtime(package: str = "ume") -> dict[str, Any]:
    """Load optional runtime integrations for ``package``.

    This function is intentionally explicit so service entry points can opt in to
    heavyweight imports (vector backends, embedding listeners, optional graph
    backends) rather than triggering them during ``import ume``.
    """

    package_module = sys.modules.get(package)
    if package_module is None:
        package_module = import_module(package)

    exports: dict[str, Any] = {
        "config": None,
        "Settings": None,
        "Neo4jGraph": None,
        "VectorBackend": None,
        "VectorStore": None,
        "VectorStoreListener": None,
        "create_default_store": None,
        "FaissBackend": None,
        "ChromaBackend": None,
        "generate_embedding": None,
        "OntologyListener": None,
        "configure_ontology_graph": None,
    }

    config_module, settings_type = load_config(package)
    exports["config"] = config_module
    exports["Settings"] = settings_type

    exports["Neo4jGraph"] = load_neo4j(package)

    (
        exports["VectorBackend"],
        exports["VectorStore"],
        exports["VectorStoreListener"],
        exports["create_default_store"],
        exports["FaissBackend"],
        exports["ChromaBackend"],
    ) = load_vector_modules(package)

    listeners_module = import_module(f"{package}._internal.listeners")
    register_listener = listeners_module.register_listener
    (
        exports["generate_embedding"],
        exports["OntologyListener"],
        exports["configure_ontology_graph"],
    ) = load_embedding(package, register_listener)

    for name, value in exports.items():
        setattr(package_module, name, value)

    setattr(package_module, "_runtime_bootstrapped", True)
    return exports
