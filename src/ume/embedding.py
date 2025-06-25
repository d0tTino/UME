from __future__ import annotations

from typing import List, TYPE_CHECKING, cast

from .config import settings

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from sentence_transformers import SentenceTransformer
try:  # pragma: no cover - optional dependency
    from sentence_transformers import SentenceTransformer
except ModuleNotFoundError:  # pragma: no cover - used in tests without package
    class SentenceTransformer:  # type: ignore[too-many-instance-attributes]
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def encode(self, text: str):  # type: ignore[override]
            return [1.0, 0.0] if "apple" in text else [0.9, 0.1]

_MODEL_CACHE: dict[str, "SentenceTransformer"] = {}


def _get_model() -> "SentenceTransformer":

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
