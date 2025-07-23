from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Dossier:
    """User dossier backed by modular YAML files."""

    root: Path
    schema_version: int = 1
    shareable: bool = False
    profile: dict[str, Any] = field(default_factory=dict)
    projects: list[dict[str, Any]] = field(default_factory=list)
    preferences: dict[str, Any] = field(default_factory=dict)
    reflections: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def load(cls, root: str | Path | None = None) -> "Dossier":
        """Load dossier from ``root`` or ``UME_DOSSIER_PATH``."""
        default = os.environ.get("UME_DOSSIER_PATH", "~/.ume_dossier")
        path_str = str(root) if root is not None else default
        path = Path(path_str).expanduser()
        obj = cls(path)
        obj._ensure_dirs()
        obj._load_files()
        return obj

    @classmethod
    def init_dossier(cls, path: str | Path) -> "Dossier":
        """Create a dossier at ``path`` using the template."""
        path = Path(path)
        template = Path(__file__).parent / "dossier_template"
        if not path.exists():
            shutil.copytree(template, path)
        return cls.load(path)

    def save(self) -> None:
        """Persist current state to disk."""
        self.root.mkdir(parents=True, exist_ok=True)
        yaml.safe_dump(
            {"schema_version": self.schema_version, "shareable": self.shareable},
            (self.root / "meta.yaml").open("w", encoding="utf-8"),
        )
        yaml.safe_dump(self.profile, (self.root / "profile.yaml").open("w", encoding="utf-8"))
        yaml.safe_dump({"projects": self.projects}, (self.root / "projects.yaml").open("w", encoding="utf-8"))
        yaml.safe_dump(self.preferences, (self.root / "preferences.yaml").open("w", encoding="utf-8"))
        yaml.safe_dump(self.reflections, (self.root / "reflections.yaml").open("w", encoding="utf-8"))

    def _ensure_dirs(self) -> None:
        (self.root / "telemetry").mkdir(parents=True, exist_ok=True)

    def _load_files(self) -> None:
        meta = self._read_yaml(self.root / "meta.yaml") or {}
        self.schema_version = int(meta.get("schema_version", self.schema_version))
        self.shareable = bool(meta.get("shareable", self.shareable))
        self.profile = self._read_yaml(self.root / "profile.yaml") or {}
        proj = self._read_yaml(self.root / "projects.yaml") or {}
        if isinstance(proj, dict):
            self.projects = proj.get("projects", [])
        else:
            self.projects = proj
        self.preferences = self._read_yaml(self.root / "preferences.yaml") or {}
        self.reflections = self._read_yaml(self.root / "reflections.yaml") or []

    @staticmethod
    def _read_yaml(path: Path) -> Any:
        if not path.is_file():
            return None
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or None


# Helper functions

def add_reflection(dossier: Dossier, text: str) -> None:
    dossier.reflections.append({"text": text, "timestamp": datetime.utcnow().isoformat()})
    dossier.save()

def list_projects(dossier: Dossier) -> list[str]:
    return [p.get("name", "") for p in dossier.projects]

def update_preferences(dossier: Dossier, **prefs: Any) -> None:
    dossier.preferences.update(prefs)
    dossier.save()
