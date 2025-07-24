from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
import json

from filelock import FileLock

import yaml

try:
    from cryptography.fernet import Fernet
except Exception:  # pragma: no cover - cryptography optional
    Fernet = None

from ..config import settings

ENCRYPTION_ENABLED = settings.UME_ENCRYPTION_ENABLED
if ENCRYPTION_ENABLED:
    if not (Fernet and settings.UME_ENCRYPTION_KEY):
        raise ValueError(
            "Encryption enabled but cryptography not available or key not set"
        )
    _fernet = Fernet(settings.UME_ENCRYPTION_KEY.encode())
else:
    _fernet = None


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
    telemetry_files: list[str] = field(default_factory=list)

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
        lock = FileLock(str(self.root / ".dossier.lock"))
        with lock:
            self._write_yaml(
                self.root / "meta.yaml",
                {
                    "schema_version": self.schema_version,
                    "shareable": self.shareable,
                    "telemetry_files": self.telemetry_files,
                },
            )
            self._write_yaml(self.root / "profile.yaml", self.profile)
            self._write_yaml(self.root / "projects.yaml", {"projects": self.projects})
            self._write_yaml(self.root / "preferences.yaml", self.preferences)
            self._write_yaml(self.root / "reflections.yaml", self.reflections)

    def _ensure_dirs(self) -> None:
        (self.root / "telemetry").mkdir(parents=True, exist_ok=True)

    def _load_files(self) -> None:
        meta = self._read_yaml(self.root / "meta.yaml") or {}
        self.schema_version = int(meta.get("schema_version", self.schema_version))
        self.shareable = bool(meta.get("shareable", self.shareable))
        self.telemetry_files = meta.get("telemetry_files", [])
        self.profile = self._read_yaml(self.root / "profile.yaml") or {}
        proj = self._read_yaml(self.root / "projects.yaml") or {}
        if isinstance(proj, dict):
            self.projects = proj.get("projects", [])
        else:
            self.projects = proj
        self.preferences = self._read_yaml(self.root / "preferences.yaml") or {}
        self.reflections = self._read_yaml(self.root / "reflections.yaml") or []

    def add_activity(self, payload: dict[str, Any]) -> None:
        """Append ``payload`` to ``telemetry/activity.log`` if allowed."""
        if not self.preferences.get("record_activity", True):
            return
        log_dir = self.root / "telemetry"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "activity.log"
        now = datetime.utcnow()
        entry = {"timestamp": now.isoformat(), "payload": payload}
        data = json.dumps(entry)

        if ENCRYPTION_ENABLED:
            token = _fernet.encrypt(data.encode()).decode()
            with log_path.open("a", encoding="utf-8") as f:
                f.write(token + "\n")
        else:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(data + "\n")

        # Daily CSV log
        csv_path = log_dir / f"{now.date().isoformat()}.csv"
        if ENCRYPTION_ENABLED:
            csv_token = _fernet.encrypt(data.encode()).decode()
            with csv_path.open("a", encoding="utf-8") as f:
                f.write(csv_token + "\n")
        else:
            if not csv_path.exists():
                with csv_path.open("w", encoding="utf-8") as f:
                    f.write("timestamp,payload\n")
            with csv_path.open("a", encoding="utf-8") as f:
                f.write(f"{now.isoformat()},{json.dumps(payload)}\n")

        # Update meta information
        rel_log = log_path.relative_to(self.root).as_posix()
        rel_csv = csv_path.relative_to(self.root).as_posix()
        updated = False
        for rel in (rel_log, rel_csv):
            if rel not in self.telemetry_files:
                self.telemetry_files.append(rel)
                updated = True
        if updated:
            lock = FileLock(str(self.root / ".dossier.lock"))
            with lock:
                self._write_yaml(
                    self.root / "meta.yaml",
                    {
                        "schema_version": self.schema_version,
                        "shareable": self.shareable,
                        "telemetry_files": self.telemetry_files,
                    },
                )

    @staticmethod
    def _read_yaml(path: Path) -> Any:
        if not path.is_file():
            return None
        if ENCRYPTION_ENABLED:
            with path.open("rb") as f:
                raw = f.read()
            if not raw:
                return None
            data = _fernet.decrypt(raw).decode()
            return yaml.safe_load(data) or None
        else:
            with path.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f) or None

    @staticmethod
    def _write_yaml(path: Path, data: Any) -> None:
        text = yaml.safe_dump(data)
        if ENCRYPTION_ENABLED:
            payload = _fernet.encrypt(text.encode())
            with path.open("wb") as f:
                f.write(payload)
        else:
            with path.open("w", encoding="utf-8") as f:
                f.write(text)


# Helper functions

def add_reflection(dossier: Dossier, text: str) -> None:
    dossier.reflections.append({"text": text, "timestamp": datetime.utcnow().isoformat()})
    dossier.save()

def list_projects(dossier: Dossier) -> list[str]:
    return [p.get("name", "") for p in dossier.projects]

def update_preferences(dossier: Dossier, **prefs: Any) -> None:
    dossier.preferences.update(prefs)
    dossier.save()
