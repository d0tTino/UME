import json
import threading
import pytest
import uuid
from ume.dossier import (
    Dossier,
    add_project,
    add_reflection,
    list_projects,
    update_preferences,
)


def test_dossier_init_and_helpers(tmp_path):
    dossier = Dossier.init_dossier(tmp_path)
    assert dossier.schema_version == Dossier.schema_version
    assert dossier.shareable is False

    pid = add_project(dossier, "demo")

    rid = add_reflection(dossier, "thinking", links=[pid])
    update_preferences(dossier, theme="dark")

    dossier.shareable = True
    dossier.save()

    reloaded = Dossier.load(tmp_path)
    assert list_projects(reloaded) == ["demo"]
    assert reloaded.preferences["theme"] == "dark"
    assert reloaded.reflections[0]["text"] == "thinking"
    assert reloaded.reflections[0]["id"] == rid
    assert reloaded.reflections[0]["links"] == [pid]
    assert reloaded.projects[0]["id"] == pid
    assert reloaded.projects[0]["links"] == []
    uuid.UUID(reloaded.projects[0]["id"])
    uuid.UUID(reloaded.reflections[0]["id"])
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
    assert not log.exists() or log.read_text() == ""

    dossier.preferences["record_activity"] = True
    dossier.save()
    dossier.add_activity({"b": 2})
    entries = [json.loads(line) for line in log.read_text().splitlines()]
    assert entries[-1]["payload"] == {"b": 2}


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
