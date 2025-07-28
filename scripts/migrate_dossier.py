#!/usr/bin/env python3
"""Upgrade dossier files to the latest schema version.

Reads ``meta.yaml``, ``profile.yaml``, ``projects.yaml``, ``preferences.yaml``,
``reflections.yaml`` and, if present, ``knowledge.yaml``, ``values.yaml`` and
``skills.yaml`` before rewriting them using the current schema.
"""
from __future__ import annotations

import argparse
import importlib
import os
from pathlib import Path
from typing import Any

import yaml

from ume.config.loader import load_settings


def _read_yaml(path: Path) -> Any:
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or None


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

    load_settings.cache_clear()
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
