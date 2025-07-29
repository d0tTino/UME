from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - type hints only
    import tiktoken as _tiktoken
else:  # pragma: no cover - optional dependency
    try:
        import tiktoken as _tiktoken
    except ModuleNotFoundError:  # pragma: no cover - allow missing dep
        _tiktoken = None  # type: ignore[assignment]


def tokenize(text: str) -> list[str]:
    """Return a list of tokens for ``text`` using ``tiktoken`` if available."""
    if _tiktoken is None:
        return text.split()
    encoding = _tiktoken.get_encoding("cl100k_base")
    token_ids = encoding.encode(text)
    return [encoding.decode([tid]) for tid in token_ids]
