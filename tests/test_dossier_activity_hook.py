import importlib
import json
import threading

import pytest

from ume.dossier import Dossier


def test_dossier_activity_hook_appends(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    Dossier.init_dossier(tmp_path)
    monkeypatch.setenv("UME_DOSSIER_PATH", str(tmp_path))
    from ume.watchers.dossier_hook import dossier_activity_hook

    dossier_activity_hook({"event": 1})

    log = tmp_path / "telemetry" / "activity.log"
    entries = [json.loads(line)["payload"] for line in log.read_text().splitlines()]
    assert entries[-1] == {"event": 1}


def test_dossier_activity_hook_concurrent(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    Dossier.init_dossier(tmp_path)
    monkeypatch.setenv("UME_DOSSIER_PATH", str(tmp_path))
    from ume.watchers.dossier_hook import dossier_activity_hook

    def worker(i: int) -> None:
        dossier_activity_hook({"n": i})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    log = tmp_path / "telemetry" / "activity.log"
    entries = [json.loads(line)["payload"] for line in log.read_text().splitlines()]
    values = sorted(e["n"] for e in entries)
    assert values == list(range(5))


def test_watcher_registration_skipped_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    import ume.watchers
    from ume.watchers import hooks

    hooks._hooks.clear()
    calls: list[object] = []
    monkeypatch.setattr(hooks, "register_hook", lambda h: calls.append(h))
    monkeypatch.setenv("UME_ACTIVITY_LOG_ENABLED", "false")
    importlib.reload(ume.watchers)

    assert not calls
