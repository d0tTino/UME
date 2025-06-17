from __future__ import annotations

import os
from typing import List

from sentence_transformers import SentenceTransformer

from .config import settings

_MODEL_CACHE: dict[str, SentenceTransformer] = {}


def _get_model() -> SentenceTransformer:
    model_name = os.getenv("UME_EMBED_MODEL", settings.UME_EMBED_MODEL)
    model = _MODEL_CACHE.get(model_name)
    if model is None:
        model = SentenceTransformer(model_name)
        _MODEL_CACHE[model_name] = model
    return model


def generate_embedding(text: str) -> List[float]:
    """Generate an embedding vector for ``text`` using Sentence Transformers."""
    model = _get_model()
    embedding = model.encode(text)
    return embedding.tolist()
