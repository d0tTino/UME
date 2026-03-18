"""Helpers for loading versioned event contract bundles."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any


_SUPPORTED_MAJORS = (1, 2, 3)


def supported_contract_majors() -> tuple[int, ...]:
    return _SUPPORTED_MAJORS


def bundle_path_for_major(major: int) -> Path:
    if major not in _SUPPORTED_MAJORS:
        raise ValueError(f"Unsupported contract major version: {major}")
    return resources.files("ume.schemas").joinpath(f"v{major}")


def load_bundle_manifest(major: int) -> dict[str, Any]:
    return load_bundle_schema(major, "bundle.json")


def load_bundle_schema(major: int, schema_name: str) -> dict[str, Any]:
    path = bundle_path_for_major(major).joinpath(schema_name)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
