from __future__ import annotations

import importlib
import logging
from typing import Any, Dict


from ._internal.listeners import GraphListener
from .config import settings
from .metrics import VECTOR_INDEX_SIZE, VECTOR_QUERY_LATENCY
from .vector_backends import (
    VectorBackend,
    FaissBackend,
    ChromaBackend,
)
from .vector_backends.faiss_backend import faiss as _faiss

# ``VectorStore`` used to point to the default FAISS backend. Preserve this
# alias for backward compatibility so callers can instantiate a vector store
# directly without importing a specific backend.
VectorStore = FaissBackend
faiss = _faiss

logger = logging.getLogger(__name__)


class VectorStoreListener(GraphListener):
    """GraphListener that indexes embeddings from node attributes."""

    def __init__(self, store: VectorBackend) -> None:
        self.store = store

    def on_node_created(
        self, node_id: str, attributes: Dict[str, Any]
    ) -> None:  # pragma: no cover - simple passthrough
        emb = attributes.get("embedding")
        if isinstance(emb, list):
            self.store.add(node_id, emb)

    def on_node_updated(
        self, node_id: str, attributes: Dict[str, Any]
    ) -> None:  # pragma: no cover - simple passthrough
        emb = attributes.get("embedding")
        if isinstance(emb, list):
            self.store.add(node_id, emb)

    def on_edge_created(
        self, source_node_id: str, target_node_id: str, label: str
    ) -> None:  # pragma: no cover - unused hooks
        pass

    def on_edge_deleted(
        self, source_node_id: str, target_node_id: str, label: str
    ) -> None:  # pragma: no cover - unused hooks
        pass


def create_default_store() -> VectorBackend:  # pragma: no cover - trivial wrapper
    """Instantiate a vector store using ``ume.config.settings``."""
    backend = getattr(settings, "UME_VECTOR_BACKEND", "faiss").lower()
    module_name = f"ume.vector_backends.{backend}_backend"
    class_name = f"{backend.capitalize()}Backend"
    try:
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
    except Exception as exc:
        raise ValueError(f"Unknown vector backend: {backend}") from exc

    kwargs: Dict[str, Any] = {}
    if backend == "faiss":
        kwargs["use_gpu"] = getattr(settings, "UME_VECTOR_USE_GPU", False)

    return cls(
        dim=settings.UME_VECTOR_DIM,
        path=settings.UME_VECTOR_INDEX,
        query_latency_metric=VECTOR_QUERY_LATENCY,
        index_size_metric=VECTOR_INDEX_SIZE,
        **kwargs,
    )


# For backward compatibility ---------------------------------------------------

# ``create_vector_store`` used to be exported. Provide an alias so older imports
# continue to work without modification.
create_vector_store = create_default_store

__all__ = [
    "VectorStore",
    "VectorBackend",
    "FaissBackend",
    "ChromaBackend",
    "VectorStoreListener",
    "create_default_store",
    "create_vector_store",
]


# Ensure ``ume.vector_store`` is set when imported standalone
if __name__ == "ume.vector_store":
    import sys as _sys

    parent = _sys.modules.get("ume")
    if parent is not None and not hasattr(parent, "vector_store"):
        parent.vector_store = _sys.modules[__name__]  # type: ignore[attr-defined]
