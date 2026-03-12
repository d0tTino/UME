from __future__ import annotations

from typing import Any, Mapping

from ..legacy_transform import apply_legacy_transform


def adapt_cli_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return apply_legacy_transform(payload)
