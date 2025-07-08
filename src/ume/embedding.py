from __future__ import annotations

from typing import List, TYPE_CHECKING, cast

from .config import settings

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from sentence_transformers import SentenceTransformer as SentenceTransformerImpl
else:
    try:  # pragma: no cover - optional dependency
        from sentence_transformers import SentenceTransformer as SentenceTransformerImpl
    except ModuleNotFoundError:

        class SentenceTransformerImpl:
            def __init__(self, model_name: str) -> None:
                self.model_name = model_name

            def encode(self, text: str) -> list[float]:
                """Return a dummy embedding of the configured dimension."""
                return [0.0] * settings.UME_VECTOR_DIM


SentenceTransformer: type[SentenceTransformerImpl] = SentenceTransformerImpl

_MODEL_CACHE: dict[str, SentenceTransformerImpl] = {}


def _get_model() -> SentenceTransformerImpl:
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
    try:
        return cast(List[float], embedding.tolist())
    except AttributeError:
        return cast(List[float], list(embedding))
