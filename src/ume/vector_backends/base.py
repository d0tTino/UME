from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Dict, List


class VectorStore(ABC):
    """Abstract interface for vector store backends."""

    def __enter__(self) -> "VectorStore":  # pragma: no cover - passthrough
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:  # pragma: no cover - passthrough
        self.close()

    @abstractmethod
    def add(self, item_id: str, vector: List[float], *, persist: bool = False) -> None:
        ...

    @abstractmethod
    def add_many(self, vectors: Dict[str, List[float]], *, persist: bool = False) -> None:
        ...

    @abstractmethod
    def delete(self, item_id: str) -> None:
        ...

    @abstractmethod
    def query(self, vector: List[float], k: int = 5) -> List[str]:
        ...

    @abstractmethod
    def save(self, path: str | None = None) -> None:  # pragma: no cover - filesystem
        ...

    @abstractmethod
    def load(self, path: str | None = None) -> None:  # pragma: no cover - filesystem
        ...

    @abstractmethod
    def expire_vectors(self, max_age_seconds: int) -> None:
        ...

    @abstractmethod
    def close(self) -> None:  # pragma: no cover - filesystem
        ...

    @abstractmethod
    def get_vector_timestamps(self) -> Dict[str, int]:
        ...


# Backwards compatibility
VectorBackend = VectorStore
