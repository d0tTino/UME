#!/usr/bin/env python3
"""Upgrade dossier files to the latest schema version.

Reads ``meta.yaml``, ``profile.yaml``, ``projects.yaml``, ``preferences.yaml``,
``reflections.yaml`` and, if present, ``knowledge.yaml``, ``values.yaml`` and
``skills.yaml`` before rewriting them using the current schema.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

# Ensure the repo root (which provides a minimal ``yaml`` fallback) is on the
# path before importing ``yaml``. When executed from the ``scripts`` directory
# the root isn't otherwise discoverable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import yaml  # type: ignore  # noqa: E402

# Make the ``ume`` package importable without installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Provide minimal stubs for optional dependencies when running as a standalone
# script so the migration can proceed without heavy extras installed.
import types

if importlib.util.find_spec("prometheus_client") is None:
    prom = types.ModuleType("prometheus_client")

    class _Metric:  # pragma: no cover - trivial stub
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def labels(self, *_: object, **__: object) -> "_Metric":
            return self

        def inc(self, *_: object, **__: object) -> None:
            pass

        def set(self, *_: object, **__: object) -> None:
            pass

    prom.Counter = prom.Histogram = prom.Gauge = _Metric  # type: ignore[attr-defined]
    prom.generate_latest = lambda *_: b""
    prom.CONTENT_TYPE_LATEST = "text/plain"
    sys.modules.setdefault("prometheus_client", prom)

# Lightweight stubs for other optional dependencies used by ume modules.
if importlib.util.find_spec("numpy") is None:
    numpy_stub = types.ModuleType("numpy")
    numpy_stub.asarray = lambda x, dtype=None: list(x)
    sys.modules.setdefault("numpy", numpy_stub)
    numpy_typing = types.ModuleType("numpy.typing")
    from typing import Any as _Any
    numpy_typing.NDArray = _Any  # type: ignore[attr-defined]
    sys.modules.setdefault("numpy.typing", numpy_typing)



def _read_yaml(path: Path) -> Any:
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as f:
        text = f.read()
    data = yaml.safe_load(text) or None
    if data:
        return data
    # Fallback simple parser for ``key: value`` pairs used in templates.
    result: dict[str, Any] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip('"')
        if value.lower() in {"true", "false"}:
            parsed: Any = value.lower() == "true"
        else:
            try:
                parsed = int(value)
            except ValueError:
                parsed = value
        result[key.strip()] = parsed
    return result or None


def _load_plain(root: Path) -> dict[str, Any]:
    meta = _read_yaml(root / "meta.yaml") or {}
    profile = _read_yaml(root / "profile.yaml") or {}
    projects = _read_yaml(root / "projects.yaml") or {}
    preferences = _read_yaml(root / "preferences.yaml") or {}
    reflections = _read_yaml(root / "reflections.yaml") or []
    knowledge = _read_yaml(root / "knowledge.yaml") or []
    values = _read_yaml(root / "values.yaml") or []
    skills = _read_yaml(root / "skills.yaml") or []
    goals = _read_yaml(root / "goals.yaml") or []

    if isinstance(projects, dict):
        projects = projects.get("projects", [])

    return {
        "schema_version": int(meta.get("schema_version", 2)),
        "shareable": bool(meta.get("shareable", False)),
        "shareable_projects": bool(
            meta.get("shareable_projects", meta.get("shareable", False))
        ),
        "shareable_reflections": bool(
            meta.get("shareable_reflections", meta.get("shareable", False))
        ),
        "telemetry_files": meta.get("telemetry_files", []),
        "profile": profile,
        "projects": projects,
        "preferences": preferences,
        "reflections": reflections,
        "knowledge": knowledge,
        "values": values,
        "skills": skills,
        "goals": goals,
    }


def migrate_dossier(path: Path, *, encrypt: bool = False) -> None:
    data = _load_plain(path)

    if encrypt:
        os.environ.setdefault("UME_ENCRYPTION_ENABLED", "true")
        if not os.environ.get("UME_ENCRYPTION_KEY"):
            from cryptography.fernet import Fernet

            key = Fernet.generate_key().decode()
            os.environ["UME_ENCRYPTION_KEY"] = key
            print(f"Generated UME_ENCRYPTION_KEY={key}")

    import ume.dossier as dossier_mod
    importlib.reload(dossier_mod)

    dossier = dossier_mod.Dossier(path)
    dossier.schema_version = dossier_mod.Dossier.schema_version
    dossier.shareable = data["shareable"]
    dossier.shareable_projects = data["shareable_projects"]
    dossier.shareable_reflections = data["shareable_reflections"]
    dossier.profile = data["profile"]
    dossier.projects = data["projects"]
    dossier.preferences = data["preferences"]
    dossier.reflections = data["reflections"]
    dossier.knowledge = data["knowledge"]
    dossier.values = data["values"]
    dossier.skills = data["skills"]
    dossier.goals = data["goals"]
    dossier.telemetry_files = data["telemetry_files"]
    dossier.save()
    print(f"Migrated dossier at {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        help="Dossier directory. Defaults to UME_DOSSIER_PATH",
        default=None,
    )
    parser.add_argument(
        "--encrypt",
        action="store_true",
        help="Rewrite files using encryption settings",
    )
    args = parser.parse_args()
    root = (
        Path(args.path).expanduser()
        if args.path is not None
        else Path(os.environ.get("UME_DOSSIER_PATH", "~/.ume_dossier")).expanduser()
    )
    migrate_dossier(root, encrypt=args.encrypt)


if __name__ == "__main__":  # pragma: no cover - script entry
    main()
