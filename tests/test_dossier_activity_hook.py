import json
import threading

import pytest

from ume.dossier import Dossier
from ume.watchers.dossier_hook import dossier_activity_hook


def test_dossier_activity_hook_appends(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    Dossier.init_dossier(tmp_path)
    monkeypatch.setenv("UME_DOSSIER_PATH", str(tmp_path))

    dossier_activity_hook({"event": 1})

    log = tmp_path / "telemetry" / "activity.log"
    entries = [json.loads(line)["payload"] for line in log.read_text().splitlines()]
    assert entries[-1] == {"event": 1}


def test_dossier_activity_hook_concurrent(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    Dossier.init_dossier(tmp_path)
    monkeypatch.setenv("UME_DOSSIER_PATH", str(tmp_path))

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
