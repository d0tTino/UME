from importlib import import_module
import sys
import types
from typing import Callable, Any, Tuple, Type

__all__ = [
    "load_vector_modules",
]

def load_vector_modules(package: str) -> Tuple[
    Type[Any],
    Type[Any],
    Type[Any],
    Callable[..., Any],
    Type[Any],
    Type[Any],
]:
    """Load vector-store related classes, returning a tuple."""
    try:
        vs = import_module(f"{package}.vector_store")
        backends = import_module(f"{package}.vector_backends")
        return (
            vs.VectorBackend,
            vs.VectorStore,
            vs.VectorStoreListener,
            vs.create_default_store,
            backends.FaissBackend,
            backends.ChromaBackend,
        )
    except Exception:
        stub = types.ModuleType(f"{package}.vector_store")

        class VectorStore:
            def __init__(self, *_: object, **__: object) -> None:
                raise ImportError("faiss is required for VectorStore")

        class VectorStoreListener:
            def __init__(self, *_: object, **__: object) -> None:
                raise ImportError("faiss is required for VectorStoreListener")

        def create_default_store(*_: object, **__: object) -> None:
            raise ImportError("faiss is required for create_default_store")

        stub.VectorStore = VectorStore  # type: ignore[attr-defined]
        stub.VectorBackend = VectorStore  # type: ignore[attr-defined]
        stub.FaissBackend = VectorStore  # type: ignore[attr-defined]
        stub.ChromaBackend = VectorStore  # type: ignore[attr-defined]
        stub.VectorStoreListener = VectorStoreListener  # type: ignore[attr-defined]
        stub.create_default_store = create_default_store  # type: ignore[attr-defined]
        sys.modules[f"{package}.vector_store"] = stub
        setattr(sys.modules[package], "vector_store", stub)
        return (
            stub.VectorBackend,
            stub.VectorStore,
            stub.VectorStoreListener,
            stub.create_default_store,
            stub.FaissBackend,
            stub.ChromaBackend,
        )
