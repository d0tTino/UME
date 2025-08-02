from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - type hints only
    import unitok as _unitok
    import tatitok as _tatitok
    import tiktoken as _tiktoken
else:  # pragma: no cover - optional dependencies
    try:
        import unitok as _unitok
    except ModuleNotFoundError:  # pragma: no cover - allow missing dep
        _unitok = None  # type: ignore[assignment]
    try:
        import tatitok as _tatitok
    except ModuleNotFoundError:  # pragma: no cover - allow missing dep
        _tatitok = None  # type: ignore[assignment]
    try:
        import tiktoken as _tiktoken
    except ModuleNotFoundError:  # pragma: no cover - allow missing dep
        _tiktoken = None  # type: ignore[assignment]


def tokenize(text: str) -> list[str]:
    """Return a list of tokens for ``text`` using available tokenizers."""
    if _unitok is not None and hasattr(_unitok, "tokenize"):
        return list(_unitok.tokenize(text))
    if _tatitok is not None and hasattr(_tatitok, "tokenize"):
        return list(_tatitok.tokenize(text))
    if _tiktoken is not None:
        encoding = _tiktoken.get_encoding("cl100k_base")
        token_ids = encoding.encode(text)
        return [encoding.decode([tid]) for tid in token_ids]
    return text.split()
