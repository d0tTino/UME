from ume.dossier import Dossier


def test_dossier_snapshot_scheduler_logs_error(tmp_path, monkeypatch, caplog):
    from ume.dossier import scheduler

    dossier = Dossier.init_dossier(tmp_path)

    def raise_error() -> None:
        raise ValueError("snap error")

    monkeypatch.setattr(dossier, "snapshot", raise_error)

    events: dict[str, bool] = {}

    class DummyEvent:
        def __init__(self) -> None:
            self.calls = 0

        def wait(self, timeout=None):
            self.calls += 1
            return self.calls > 1

        def set(self):
            events["set"] = True

    class DummyThread:
        def __init__(self, target=None, daemon=None):
            self._target = target

        def start(self):
            self._target()

        def join(self):
            events["joined"] = True

        def is_alive(self):
            return True

    monkeypatch.setattr(scheduler.threading, "Event", DummyEvent)
    monkeypatch.setattr(scheduler.threading, "Thread", DummyThread)

    with caplog.at_level("ERROR", logger="ume.dossier.scheduler"):
        scheduler.start_dossier_snapshot_scheduler(dossier, interval_seconds=1)

    scheduler.stop_dossier_snapshot_scheduler()

    assert any("Failed to snapshot dossier" in r.message for r in caplog.records)
    assert events.get("set") and events.get("joined")
