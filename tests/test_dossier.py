import json
import threading
from datetime import datetime
import yaml
import pytest
from ume.dossier import (
    Dossier,
    add_reflection,
    list_projects,
    update_preferences,
)


def test_dossier_init_and_helpers(tmp_path):
    dossier = Dossier.init_dossier(tmp_path)
    assert dossier.schema_version == Dossier.schema_version
    assert dossier.shareable is False

    dossier.projects.append({"name": "demo"})
    dossier.save()

    add_reflection(dossier, "thinking")
    update_preferences(dossier, theme="dark")

    dossier.shareable = True
    dossier.save()

    reloaded = Dossier.load(tmp_path)
    assert list_projects(reloaded) == ["demo"]
    assert reloaded.preferences["theme"] == "dark"
    assert reloaded.reflections[0]["text"] == "thinking"
    assert reloaded.shareable is True


def test_dossier_env_load(tmp_path, monkeypatch):
    Dossier.init_dossier(tmp_path)
    monkeypatch.setenv("UME_DOSSIER_PATH", str(tmp_path))
    dossier = Dossier.load()
    assert dossier.root == tmp_path


def test_add_activity_respects_preferences(tmp_path):
    dossier = Dossier.init_dossier(tmp_path)
    dossier.preferences["record_activity"] = False
    dossier.save()

    dossier.add_activity({"a": 1})
    log = tmp_path / "telemetry" / "activity.log"
    csv = tmp_path / "telemetry" / f"{datetime.utcnow().date().isoformat()}.csv"
    meta = yaml.safe_load((tmp_path / "meta.yaml").read_text())
    assert not log.exists() or log.read_text() == ""
    assert not csv.exists()
    assert meta.get("telemetry_files", []) == []

    dossier.preferences["record_activity"] = True
    dossier.save()
    dossier.add_activity({"b": 2})
    entries = [json.loads(line) for line in log.read_text().splitlines()]
    assert entries[-1]["payload"] == {"b": 2}
    assert csv.exists()
    meta = yaml.safe_load((tmp_path / "meta.yaml").read_text())
    assert sorted(meta.get("telemetry_files", [])) == sorted([
        "telemetry/activity.log",
        f"telemetry/{datetime.utcnow().date().isoformat()}.csv",
    ])


def test_add_activity_thread_safety(tmp_path):
    dossier = Dossier.init_dossier(tmp_path)
    dossier.preferences["record_activity"] = True
    dossier.save()

    def worker(i: int) -> None:
        dossier.add_activity({"n": i})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    log = tmp_path / "telemetry" / "activity.log"
    entries = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(entries) == 5


def test_dossier_encryption_roundtrip(tmp_path, monkeypatch):
    import importlib
    try:
        from cryptography.fernet import Fernet
    except Exception:
        pytest.skip("cryptography not available")
    from ume.config.loader import load_settings

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("UME_ENCRYPTION_ENABLED", "true")
    monkeypatch.setenv("UME_ENCRYPTION_KEY", key)
    monkeypatch.setenv("UME_DOSSIER_PATH", str(tmp_path))

    import ume.config as cfg
    load_settings.cache_clear()
    importlib.reload(cfg)
    import ume.dossier as dossier_mod
    importlib.reload(dossier_mod)

    dossier = dossier_mod.Dossier.init_dossier(tmp_path)
    dossier.profile["name"] = "Alice"
    dossier.preferences["record_activity"] = True
    dossier.save()
    dossier.add_activity({"act": 1})

    raw = (tmp_path / "profile.yaml").read_bytes()
    assert b"Alice" not in raw
    log_raw = (tmp_path / "telemetry" / "activity.log").read_bytes()
    assert b"act" not in log_raw

    importlib.reload(dossier_mod)
    reloaded = dossier_mod.Dossier.load(tmp_path)
    assert reloaded.profile["name"] == "Alice"


def test_add_activity_multiple_files(tmp_path, monkeypatch):
    dossier = Dossier.init_dossier(tmp_path)
    dossier.preferences["record_activity"] = True
    dossier.save()

    class D1:
        @staticmethod
        def utcnow():
            return datetime(2023, 1, 1, 0, 0, 0)

    class D2:
        @staticmethod
        def utcnow():
            return datetime(2023, 1, 2, 0, 0, 0)

    import ume.dossier as dossier_mod
    monkeypatch.setattr(dossier_mod, "datetime", D1)
    dossier.add_activity({"n": 1})
    monkeypatch.setattr(dossier_mod, "datetime", D2)
    dossier.add_activity({"n": 2})

    meta = yaml.safe_load((tmp_path / "meta.yaml").read_text())
    expected = {
        "telemetry/activity.log",
        "telemetry/2023-01-01.csv",
        "telemetry/2023-01-02.csv",
    }
    assert set(meta.get("telemetry_files", [])) == expected
