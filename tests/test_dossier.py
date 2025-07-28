import json
import multiprocessing as mp
from datetime import datetime
import yaml
import pytest
import uuid
from ume.config import settings
from ume.dossier import (
    Dossier,
    add_project,
    add_reflection,
    add_memory,
    add_value,
    add_skill,
    add_goal,
    list_reflections,
    list_projects,
    list_skills,
    list_goals,
    list_memories,
    update_preferences,
)


def _activity_worker(path: str, i: int) -> None:
    dossier = Dossier.load(path)
    dossier.add_activity({"n": i})


def test_dossier_init_and_helpers(tmp_path):
    dossier = Dossier.init_dossier(tmp_path)
    assert dossier.schema_version == Dossier.schema_version
    assert dossier.shareable is False
    assert dossier.shareable_projects is False
    assert dossier.shareable_reflections is False
    assert dossier.shareable_skills is False
    assert dossier.shareable_values is False
    assert dossier.shareable_memories is False

    pid = add_project(dossier, "demo", attachments=["file.txt"])

    rid = add_reflection(dossier, "thinking", links=[pid], attachments=["img.png"])
    mid = add_memory(dossier, "fact", links=[rid])
    add_value(dossier, "honesty")
    add_skill(dossier, "python")
    add_goal(dossier, "improve")
    update_preferences(dossier, theme="dark")

    dossier.shareable = True
    dossier.shareable_projects = True
    dossier.shareable_reflections = True
    dossier.shareable_skills = True
    dossier.shareable_values = True
    dossier.shareable_memories = True
    dossier.save()

    reloaded = Dossier.load(tmp_path)
    assert list_projects(reloaded) == ["demo"]
    assert reloaded.preferences["theme"] == "dark"
    assert reloaded.reflections[0]["text"] == "thinking"
    assert reloaded.reflections[0]["id"] == rid
    assert reloaded.reflections[0]["links"] == [pid]
    assert reloaded.reflections[0]["attachments"] == ["img.png"]
    assert reloaded.knowledge[0]["text"] == "fact"
    assert reloaded.knowledge[0]["links"] == [rid]
    assert reloaded.knowledge[0]["id"] == mid
    assert reloaded.values == ["honesty"]
    assert list_reflections(reloaded) == ["thinking"]
    assert list_memories(reloaded) == ["fact"]
    assert list_skills(reloaded) == ["python"]
    assert list_goals(reloaded) == ["improve"]
    assert reloaded.projects[0]["id"] == pid
    assert reloaded.projects[0]["links"] == []
    assert reloaded.projects[0]["attachments"] == ["file.txt"]
    uuid.UUID(reloaded.projects[0]["id"])
    uuid.UUID(reloaded.reflections[0]["id"])
    assert reloaded.shareable is True
    assert reloaded.shareable_projects is True
    assert reloaded.shareable_reflections is True
    assert reloaded.shareable_skills is True
    assert reloaded.shareable_values is True
    assert reloaded.shareable_memories is True


def test_dossier_env_load(tmp_path, monkeypatch):
    Dossier.init_dossier(tmp_path)
    monkeypatch.setattr(settings, "UME_DOSSIER_PATH", str(tmp_path), raising=False)
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

    procs = [
        mp.Process(target=_activity_worker, args=(str(tmp_path), i))
        for i in range(5)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()

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
    monkeypatch.setattr(settings, "UME_DOSSIER_PATH", str(tmp_path), raising=False)

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

    # Reset encryption settings and reload modules to avoid cross-test effects
    monkeypatch.delenv("UME_ENCRYPTION_ENABLED", raising=False)
    monkeypatch.delenv("UME_ENCRYPTION_KEY", raising=False)
    load_settings.cache_clear()
    importlib.reload(cfg)
    importlib.reload(dossier_mod)


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


def test_dossier_snapshot(tmp_path):
    dossier = Dossier.init_dossier(tmp_path)
    snap_dir = dossier.snapshot()
    assert snap_dir.parent == tmp_path / "history"
    originals = {p.name for p in tmp_path.glob("*.yaml")}
    copies = {p.name for p in snap_dir.glob("*.yaml")}
    assert originals == copies


def test_add_knowledge_and_listing(tmp_path):
    dossier = Dossier.init_dossier(tmp_path)
    add_value(dossier, "integrity")
    add_value(dossier, "integrity")
    add_skill(dossier, "rust")
    add_skill(dossier, "rust")
    add_goal(dossier, "x")
    add_goal(dossier, "x")

    assert dossier.values == ["integrity"]
    assert list_skills(dossier) == ["rust"]
    assert list_goals(dossier) == ["x"]

    loaded = Dossier.load(tmp_path)
    assert loaded.values == ["integrity"]
    assert list_skills(loaded) == ["rust"]
    assert list_goals(loaded) == ["x"]


def test_encrypted_knowledge_roundtrip(tmp_path, monkeypatch):
    import importlib

    try:
        from cryptography.fernet import Fernet
    except Exception:
        pytest.skip("cryptography not available")

    from ume.config.loader import load_settings

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("UME_ENCRYPTION_ENABLED", "true")
    monkeypatch.setenv("UME_ENCRYPTION_KEY", key)
    monkeypatch.setattr(settings, "UME_DOSSIER_PATH", str(tmp_path), raising=False)

    import ume.config as cfg
    load_settings.cache_clear()
    importlib.reload(cfg)
    import ume.dossier as dossier_mod
    importlib.reload(dossier_mod)

    dossier = dossier_mod.Dossier.init_dossier(tmp_path)
    dossier_mod.add_value(dossier, "transparency")
    dossier_mod.add_skill(dossier, "go")
    dossier_mod.add_goal(dossier, "g")

    raw_v = (tmp_path / "values.yaml").read_bytes()
    raw_s = (tmp_path / "skills.yaml").read_bytes()
    raw_g = (tmp_path / "goals.yaml").read_bytes()
    assert b"transparency" not in raw_v
    assert b"go" not in raw_s
    assert raw_g.strip() != b"g"

    reloaded = dossier_mod.Dossier.load(tmp_path)
    assert "transparency" in reloaded.values
    assert "go" in reloaded.skills
    assert "g" in reloaded.goals

    # Reset encryption settings and reload modules
    monkeypatch.delenv("UME_ENCRYPTION_ENABLED", raising=False)
    monkeypatch.delenv("UME_ENCRYPTION_KEY", raising=False)
    load_settings.cache_clear()
    importlib.reload(cfg)
    importlib.reload(dossier_mod)
