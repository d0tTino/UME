from __future__ import annotations

from typing import List, TYPE_CHECKING, cast

from .config import settings

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from sentence_transformers import SentenceTransformer

_MODEL_CACHE: dict[str, "SentenceTransformer"] = {}


def _get_model() -> "SentenceTransformer":
    from sentence_transformers import SentenceTransformer

    model_name = settings.UME_EMBED_MODEL
    model = _MODEL_CACHE.get(model_name)
    if model is None:
        model = SentenceTransformer(model_name)
        _MODEL_CACHE[model_name] = model
    return model


def generate_embedding(text: str) -> List[float]:
    """Generate an embedding vector for ``text`` using Sentence Transformers."""
    model = _get_model()
    embedding = model.encode(text)
    return cast(List[float], embedding.tolist())
