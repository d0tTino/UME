import os
import sys
import shutil
import importlib
import subprocess
from pathlib import Path

import yaml
import pytest

from ume.dossier import Dossier
from ume.config.loader import load_settings

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "migrate_dossier.py"
TEMPLATE = Path(__file__).resolve().parents[1] / "src/ume/dossier/dossier_template"


def _make_dossier(tmp_path: Path) -> Path:
    root = tmp_path / "dossier"
    shutil.copytree(TEMPLATE, root)
    meta = yaml.safe_load((root / "meta.yaml").read_text())
    meta["schema_version"] = 0
    (root / "meta.yaml").write_text(yaml.safe_dump(meta))
    return root


def test_migrate_inplace(tmp_path: Path) -> None:
    root = _make_dossier(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(root)],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert proc.returncode == 0
    meta = yaml.safe_load((root / "meta.yaml").read_text())
    assert meta["schema_version"] == Dossier.schema_version


def test_migrate_with_encrypt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    try:
        from cryptography.fernet import Fernet
    except Exception:
        pytest.skip("cryptography not available")

    root = _make_dossier(tmp_path)
    key = Fernet.generate_key().decode()
    env = os.environ.copy()
    env["UME_ENCRYPTION_ENABLED"] = "true"
    env["UME_ENCRYPTION_KEY"] = key
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--encrypt", str(root)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0
    raw = (root / "profile.yaml").read_bytes()
    assert b"Your Name" not in raw

    monkeypatch.setenv("UME_ENCRYPTION_ENABLED", "true")
    monkeypatch.setenv("UME_ENCRYPTION_KEY", key)
    import ume.config as cfg
    load_settings.cache_clear()
    importlib.reload(cfg)
    import ume.dossier as dossier_mod
    importlib.reload(dossier_mod)
    dossier = dossier_mod.Dossier.load(root)
    assert dossier.schema_version == Dossier.schema_version
    assert dossier.profile["name"] == "Your Name"
