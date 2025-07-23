import json
import threading
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
