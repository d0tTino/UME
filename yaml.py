"""Minimal YAML-compatible helpers.

Provides ``safe_load`` and ``safe_dump`` using the standard :mod:`json`
module so the codebase can operate without the optional PyYAML
dependency. Only JSON-compatible YAML documents are supported, which
covers the simple structures used in tests.
"""
from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any, IO, Union

Data = Union[str, bytes, IO[str], IO[bytes], None]


def safe_load(data: Data) -> Any:
    """Parse *data* into Python objects.

    Accepts strings, bytes or file-like objects and returns ``None`` for empty
    input to mirror :func:`yaml.safe_load`.
    If parsing fails, an empty dict is returned as a permissive fallback.
    """
    if hasattr(data, "read"):
        data = data.read()  # type: ignore[assignment]
    if not data:
        return None
    if isinstance(data, bytes):
        data = data.decode()
    data = data.strip()
    if not data:
        return None
    try:
        return json.loads(data)
    except JSONDecodeError:
        return {}


def safe_dump(obj: Any, *args: Any, **kwargs: Any) -> str:
    """Serialize *obj* to a YAML string using JSON syntax."""
    return json.dumps(obj, *args, **kwargs)


__all__ = ["safe_load", "safe_dump"]
