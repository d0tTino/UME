from __future__ import annotations

from typing import Dict, Iterable
import logging
import numbers
import time

from ..config import settings
from ..vector_store import VectorBackend

try:  # optional dependency
    import pinecone
except Exception:  # pragma: no cover - optional dependency missing
    pinecone = None

logger = logging.getLogger(__name__)


class PineconeBackend(VectorBackend):
    """Vector backend backed by a Pinecone index."""

    def __init__(
        self,
        dim: int,
        *,
        api_key: str | None = None,
        environment: str | None = None,
        index_name: str | None = None,
    ) -> None:
        if pinecone is None:
            raise ImportError(
                "pinecone-client is required for PineconeBackend. Install it with 'poetry install pinecone-client'"
            )
        self.dim = dim
        api_key = api_key or settings.UME_PINECONE_API_KEY
        environment = environment or settings.UME_PINECONE_ENVIRONMENT
        index_name = index_name or settings.UME_PINECONE_INDEX
        pinecone.init(api_key=api_key, environment=environment)
        self.index = pinecone.Index(index_name)
        self.vector_ts: Dict[str, int] = {}

    def add(self, item_id: str, vector: list[float], *, persist: bool = False) -> None:
        if (
            not isinstance(vector, Iterable)
            or isinstance(vector, (str, bytes))
            or not all(isinstance(v, numbers.Real) for v in vector)
        ):
            raise ValueError("vector must be an iterable of numbers")
        self.index.upsert([(item_id, vector)])
        self.vector_ts[item_id] = int(time.time())

    def add_many(self, vectors: Dict[str, list[float]], *, persist: bool = False) -> None:
        if not vectors:
            return
        self.index.upsert(list(vectors.items()))
        now = int(time.time())
        for vid in vectors:
            self.vector_ts[vid] = now

    def delete(self, item_id: str) -> None:
        self.index.delete(ids=[item_id])
        self.vector_ts.pop(item_id, None)

    def query(self, vector: list[float], k: int = 5) -> list[str]:
        if (
            not isinstance(vector, Iterable)
            or isinstance(vector, (str, bytes))
            or not all(isinstance(v, numbers.Real) for v in vector)
        ):
            raise ValueError("vector must be an iterable of numbers")
        res = self.index.query(vector=vector, top_k=k)
        matches = getattr(res, "matches", res.get("matches", []))
        return [m.id if hasattr(m, "id") else m["id"] for m in matches]

    def save(self, path: str | None = None) -> None:  # pragma: no cover - remote
        pass

    def load(self, path: str | None = None) -> None:  # pragma: no cover - remote
        pass

    def close(self) -> None:  # pragma: no cover - remote
        pass

    def get_vector_timestamps(self) -> Dict[str, int]:
        return dict(self.vector_ts)

    def expire_vectors(self, max_age_seconds: int) -> None:
        cutoff = int(time.time()) - max_age_seconds
        to_delete = [k for k, ts in self.vector_ts.items() if ts < cutoff]
        for vid in to_delete:
            self.delete(vid)
