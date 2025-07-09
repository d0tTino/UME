from __future__ import annotations

from typing import Any, Dict, List, TYPE_CHECKING
from types import TracebackType

from .config import settings

from ._internal.listeners import GraphListener
from .metrics import VECTOR_INDEX_SIZE, VECTOR_QUERY_LATENCY


def _resolve_vector_dim(config_dim: int) -> int:
    """Validate or infer the vector dimension."""
    from .embedding import generate_embedding

    actual_dim = len(generate_embedding("test"))
    if config_dim == 0:
        settings.UME_VECTOR_DIM = actual_dim
        return actual_dim
    if config_dim != actual_dim:
        raise ValueError(
            f"UME_VECTOR_DIM ({config_dim}) does not match embedding model dimension ({actual_dim})"
        )
    return config_dim

class VectorBackend:
    """Abstract interface for vector store backends."""

    def __enter__(self) -> "VectorBackend":  # pragma: no cover - passthrough
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:  # pragma: no cover - passthrough
        self.close()

    def add(self, item_id: str, vector: List[float], *, persist: bool = False) -> None:
        raise NotImplementedError

    def add_many(self, vectors: Dict[str, List[float]], *, persist: bool = False) -> None:
        raise NotImplementedError

    def delete(self, item_id: str) -> None:
        raise NotImplementedError

    def query(self, vector: List[float], k: int = 5) -> List[str]:
        raise NotImplementedError

    def save(self, path: str | None = None) -> None:  # pragma: no cover - filesystem
        raise NotImplementedError

    def load(self, path: str | None = None) -> None:  # pragma: no cover - filesystem
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - filesystem
        raise NotImplementedError

    def get_vector_timestamps(self) -> Dict[str, int]:
        raise NotImplementedError

    def expire_vectors(self, max_age_seconds: int) -> None:
        """Delete vectors older than ``max_age_seconds``."""
        raise NotImplementedError


from .vector_backends import FaissBackend, ChromaBackend, get_backend  # noqa: F401,E402


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
    backend_name = settings.UME_VECTOR_BACKEND.lower()
    cls = get_backend(backend_name)
    kwargs: Dict[str, Any] = {}
    if cls is FaissBackend:
        kwargs["use_gpu"] = settings.UME_VECTOR_USE_GPU
    dim = _resolve_vector_dim(settings.UME_VECTOR_DIM)
    return cls(
        dim=dim,
        path=settings.UME_VECTOR_INDEX,
        query_latency_metric=VECTOR_QUERY_LATENCY,
        index_size_metric=VECTOR_INDEX_SIZE,
        **kwargs,
    )


# For backward compatibility ---------------------------------------------------

# ``create_vector_store`` used to be exported. Provide an alias so older imports
# continue to work without modification.
create_vector_store = create_default_store


if TYPE_CHECKING:  # pragma: no cover - used for static typing only
    from typing import TypeAlias

    VectorStore: TypeAlias = VectorBackend
else:

    class VectorStore:
        """Factory for the configured vector store backend."""

        def __new__(cls, *args: Any, **kwargs: Any) -> VectorBackend:
            backend_name = settings.UME_VECTOR_BACKEND.lower()
            store_cls = get_backend(backend_name)
            dim = kwargs.pop("dim", settings.UME_VECTOR_DIM)
            kwargs["dim"] = _resolve_vector_dim(dim)
            if store_cls is FaissBackend:
                kwargs.setdefault("use_gpu", settings.UME_VECTOR_USE_GPU)
            return store_cls(*args, **kwargs)

# Ensure ``ume.vector_store`` is set when imported standalone
if __name__ == "ume.vector_store":
    import sys as _sys
    parent = _sys.modules.get("ume")
    if parent is not None and not hasattr(parent, "vector_store"):
        parent.vector_store = _sys.modules[__name__]  # type: ignore[attr-defined]

