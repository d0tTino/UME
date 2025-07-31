from __future__ import annotations

from typing import Dict, Iterable
from types import TracebackType
import logging
import time
import numbers

from ..config import settings
from ..vector_store import VectorBackend

try:  # optional dependency
    from pymilvus import MilvusClient
except Exception:  # pragma: no cover - optional dependency missing
    MilvusClient = None

logger = logging.getLogger(__name__)


class MilvusBackend(VectorBackend):
    """Milvus-based vector store backend."""

    def __init__(
        self,
        dim: int,
        *,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        collection_name: str = "ume_vectors",
    ) -> None:
        if MilvusClient is None:
            raise ImportError(
                "pymilvus is required for MilvusBackend. Install it with 'poetry install pymilvus'"
            )
        self.dim = dim
        self.collection_name = collection_name
        self.uri = uri or settings.UME_MILVUS_URI
        self.user = user or settings.UME_MILVUS_USER
        self.password = password or settings.UME_MILVUS_PASSWORD

        self.client = MilvusClient(
            uri=self.uri,
            user=self.user or "",
            password=self.password or "",
        )
        if not self.client.has_collection(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                dimension=dim,
                primary_field_name="id",
                id_type="string",
                metric_type="COSINE",
            )
            self.client.create_index(collection_name)
        self.client.load_collection(collection_name)

    def __enter__(self) -> "MilvusBackend":  # pragma: no cover - passthrough
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:  # pragma: no cover - passthrough
        self.close()

    def add(self, item_id: str, vector: list[float], *, persist: bool = False) -> None:
        self.add_many({item_id: vector})

    def add_many(self, vectors: Dict[str, list[float]], *, persist: bool = False) -> None:
        if not vectors:
            return
        data = [
            {"id": vid, "vector": vec, "ts": int(time.time())}
            for vid, vec in vectors.items()
        ]
        self.client.upsert(self.collection_name, data)

    def delete(self, item_id: str) -> None:
        self.client.delete(self.collection_name, f"id == '{item_id}'")

    def query(self, vector: list[float], k: int = 5) -> list[str]:
        if (
            not isinstance(vector, Iterable)
            or isinstance(vector, (str, bytes))
            or not all(isinstance(v, numbers.Real) for v in vector)
        ):
            raise ValueError("vector must be an iterable of numbers")
        results = self.client.search(
            self.collection_name,
            data=[vector],
            limit=k,
            output_fields=["id"],
            search_params={"metric_type": "COSINE"},
        )
        return [hit["id"] for hit in results[0]]

    def save(self, path: str | None = None) -> None:  # pragma: no cover - persistence handled by Milvus
        pass

    def load(self, path: str | None = None) -> None:  # pragma: no cover - persistence handled by Milvus
        pass

    def close(self) -> None:  # pragma: no cover - connection cleanup
        try:
            self.client.close()
        except Exception:
            logger.exception("Failed to close Milvus client")

    def get_vector_timestamps(self) -> Dict[str, int]:
        records = self.client.query(
            self.collection_name,
            expr="",
            output_fields=["id", "ts"],
        )
        return {r["id"]: int(r["ts"]) for r in records}
