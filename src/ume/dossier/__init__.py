from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4
from pathlib import Path
from typing import Any
import json

from filelock import FileLock

import yaml  # type: ignore

try:
    from cryptography.fernet import Fernet
except Exception:  # pragma: no cover - cryptography optional
    Fernet = None  # type: ignore[misc, assignment]

from ..config import settings

ENCRYPTION_ENABLED = settings.UME_ENCRYPTION_ENABLED
_fernet: Fernet | None
if ENCRYPTION_ENABLED:
    if Fernet is None or not settings.UME_ENCRYPTION_KEY:
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
    shareable_projects: bool = False
    shareable_reflections: bool = False
    profile: dict[str, Any] = field(default_factory=dict)
    projects: list[dict[str, Any]] = field(default_factory=list)
    preferences: dict[str, Any] = field(default_factory=dict)
    reflections: list[dict[str, Any]] = field(default_factory=list)
    knowledge: list[dict[str, Any]] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
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
                    "shareable_projects": self.shareable_projects,
                    "shareable_reflections": self.shareable_reflections,
                    "telemetry_files": self.telemetry_files,
                },
            )
            self._write_yaml(self.root / "profile.yaml", self.profile)
            self._write_yaml(self.root / "projects.yaml", {"projects": self.projects})
            self._write_yaml(self.root / "preferences.yaml", self.preferences)
            self._write_yaml(self.root / "reflections.yaml", self.reflections)
            self._write_yaml(self.root / "knowledge.yaml", self.knowledge)
            self._write_yaml(self.root / "values.yaml", self.values)
            self._write_yaml(self.root / "skills.yaml", self.skills)

    def _ensure_dirs(self) -> None:
        (self.root / "telemetry").mkdir(parents=True, exist_ok=True)

    def _load_files(self) -> None:
        meta = self._read_yaml(self.root / "meta.yaml") or {}
        self.schema_version = int(meta.get("schema_version", self.schema_version))
        self.shareable = bool(meta.get("shareable", self.shareable))
        self.shareable_projects = bool(
            meta.get("shareable_projects", meta.get("shareable", self.shareable))
        )
        self.shareable_reflections = bool(
            meta.get("shareable_reflections", meta.get("shareable", self.shareable))
        )
        self.telemetry_files = meta.get("telemetry_files", [])
        self.profile = self._read_yaml(self.root / "profile.yaml") or {}
        proj = self._read_yaml(self.root / "projects.yaml") or {}
        if isinstance(proj, dict):
            self.projects = proj.get("projects", [])
        else:
            self.projects = proj
        self.preferences = self._read_yaml(self.root / "preferences.yaml") or {}
        self.reflections = self._read_yaml(self.root / "reflections.yaml") or []
        self.knowledge = self._read_yaml(self.root / "knowledge.yaml") or []
        self.values = self._read_yaml(self.root / "values.yaml") or []
        self.skills = self._read_yaml(self.root / "skills.yaml") or []

        normalized_projects = []
        for p in self.projects:
            if isinstance(p, str):
                normalized_projects.append(
                    {"id": p, "name": p, "links": [], "attachments": []}
                )
            else:
                p.setdefault("id", str(uuid4()))
                p.setdefault("links", [])
                p.setdefault("attachments", [])
                normalized_projects.append(p)
        self.projects = normalized_projects

        normalized_reflections = []
        for r in self.reflections:
            r.setdefault("id", str(uuid4()))
            r.setdefault("links", [])
            r.setdefault("attachments", [])
            normalized_reflections.append(r)
        self.reflections = normalized_reflections

        normalized_knowledge = []
        for k in self.knowledge:
            k.setdefault("id", str(uuid4()))
            k.setdefault("links", [])
            k.setdefault("attachments", [])
            normalized_knowledge.append(k)
        self.knowledge = normalized_knowledge

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

        lock = FileLock(str(log_dir / ".activity.lock"))
        with lock:
            if ENCRYPTION_ENABLED:
                assert _fernet is not None
                token = _fernet.encrypt(data.encode()).decode()
                with log_path.open("a", encoding="utf-8") as f:
                    f.write(token + "\n")
            else:
                with log_path.open("a", encoding="utf-8") as f:
                    f.write(data + "\n")

            # Daily CSV log
            csv_path = log_dir / f"{now.date().isoformat()}.csv"
            if ENCRYPTION_ENABLED:
                assert _fernet is not None
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
                        "shareable_projects": self.shareable_projects,
                        "shareable_reflections": self.shareable_reflections,
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
            assert _fernet is not None
            data = _fernet.decrypt(raw).decode()
            return yaml.safe_load(data) or None
        else:
            with path.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f) or None

    @staticmethod
    def _write_yaml(path: Path, data: Any) -> None:
        text = yaml.safe_dump(data)
        if ENCRYPTION_ENABLED:
            assert _fernet is not None
            payload = _fernet.encrypt(text.encode())
            with path.open("wb") as f:
                f.write(payload)
        else:
            with path.open("w", encoding="utf-8") as f:
                f.write(text)

    def snapshot(self) -> Path:
        """Copy all YAML files into a timestamped history folder."""
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        dest = self.root / "history" / ts
        dest.mkdir(parents=True, exist_ok=True)
        for yaml_file in self.root.glob("*.yaml"):
            shutil.copy2(yaml_file, dest / yaml_file.name)
        return dest


# Helper functions

def add_project(
    dossier: Dossier,
    name: str,
    links: list[str] | None = None,
    attachments: list[str] | None = None,
) -> str:
    """Append a project entry and return its id."""
    for p in dossier.projects:
        if p.get("name") == name:
            return str(p["id"])
    entry_id = str(uuid4())
    entry = {
        "id": entry_id,
        "name": name,
        "links": links or [],
        "attachments": attachments or [],
    }
    dossier.projects.append(entry)
    dossier.save()
    return entry_id


def add_reflection(
    dossier: Dossier,
    text: str,
    links: list[str] | None = None,
    attachments: list[str] | None = None,
) -> str:
    entry_id = str(uuid4())
    entry = {
        "id": entry_id,
        "text": text,
        "timestamp": datetime.utcnow().isoformat(),
        "links": links or [],
        "attachments": attachments or [],
    }
    dossier.reflections.append(entry)
    dossier.save()
    return entry_id


def list_reflections(dossier: Dossier) -> list[str]:
    """Return a list of reflection texts."""
    return [r.get("text", "") for r in dossier.reflections]

def list_projects(dossier: Dossier) -> list[str]:
    return [p.get("name", "") for p in dossier.projects]

def update_preferences(dossier: Dossier, **prefs: Any) -> None:
    dossier.preferences.update(prefs)
    dossier.save()


def add_value(dossier: Dossier, value: str) -> None:
    """Append a value string if not present."""
    if value not in dossier.values:
        dossier.values.append(value)
        dossier.save()


def add_skill(dossier: Dossier, skill: str) -> None:
    """Append a skill string if not present."""
    if skill not in dossier.skills:
        dossier.skills.append(skill)
        dossier.save()


def list_skills(dossier: Dossier) -> list[str]:
    return list(dossier.skills)


def add_memory(
    dossier: Dossier,
    text: str,
    links: list[str] | None = None,
    attachments: list[str] | None = None,
) -> str:
    """Append a knowledge entry and return its id."""
    entry_id = str(uuid4())
    entry = {
        "id": entry_id,
        "text": text,
        "timestamp": datetime.utcnow().isoformat(),
        "links": links or [],
        "attachments": attachments or [],
    }
    dossier.knowledge.append(entry)
    dossier.save()
    return entry_id


def list_memories(dossier: Dossier) -> list[str]:
    return [m.get("text", "") for m in dossier.knowledge]
