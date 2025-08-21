"""Minimal YAML-compatible helpers.

Provides ``safe_load`` and ``safe_dump`` using the standard :mod:`json`
module so the codebase can operate without the optional PyYAML
dependency. Only JSON-compatible YAML documents are supported, which
covers the simple structures used in tests.
"""
from __future__ import annotations

import json
from json import JSONDecodeError
import io
from typing import Any, Union

Data = Union[str, bytes, io.TextIOBase, io.BufferedIOBase, None]


def safe_load(data: Data) -> Any:
    """Parse *data* into Python objects.

    Accepts strings, bytes or file-like objects and returns ``None`` for empty
    input to mirror :func:`yaml.safe_load`.
    If parsing fails, an empty dict is returned as a permissive fallback.
    """
    if data is None:
        return None
    if hasattr(data, "read"):

        data = data.read()
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
