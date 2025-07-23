import logging
from types import SimpleNamespace
from typing import Any

import pytest

from tests.test_dev_log_watcher import load_dev_log_watcher


def test_on_modified_ignores_directory(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    dev_log_watcher = load_dev_log_watcher(monkeypatch)
    messages: list[bytes] = []

    class Producer:
        def produce(self, topic: str, data: bytes) -> None:
            messages.append(data)

    handler = dev_log_watcher.DevLogHandler(Producer())
    event = SimpleNamespace(src_path=str(tmp_path), is_directory=True)
    handler.on_modified(event)

    assert messages == []


def test_on_modified_logs_error(tmp_path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    dev_log_watcher = load_dev_log_watcher(monkeypatch)

    class Producer:
        def produce(self, *_: Any, **__: Any) -> None:
            raise dev_log_watcher.KafkaException("boom")

    handler = dev_log_watcher.DevLogHandler(Producer())
    caplog.set_level(logging.ERROR)
    event = SimpleNamespace(src_path=str(tmp_path / "file.txt"), is_directory=False)
    handler.on_modified(event)

    assert any("Failed to produce dev log event" in rec.message for rec in caplog.records)


def test_run_watcher_runtime_cleanup(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Watcher stops and flushes after short runtime."""
    dev_log_watcher = load_dev_log_watcher(monkeypatch)

    class Producer:
        def __init__(self) -> None:
            self.flush_calls = 0

        def produce(self, *_: Any, **__: Any) -> None:
            pass

        def flush(self) -> None:
            self.flush_calls += 1

    class DummyObserver:
        def __init__(self) -> None:
            self.stop_calls = 0
            self.join_calls = 0
            self.scheduled: list[str] = []

        def schedule(self, handler: dev_log_watcher.DevLogHandler, path: str, recursive: bool = True) -> None:
            self.scheduled.append(path)

        def start(self) -> None:  # pragma: no cover - not used
            pass

        def join(self) -> None:
            self.join_calls += 1

        def stop(self) -> None:
            self.stop_calls += 1

    producer = Producer()
    observer = DummyObserver()
    monkeypatch.setattr(dev_log_watcher, "Producer", lambda *_, **__: producer)
    monkeypatch.setattr(dev_log_watcher, "Observer", lambda: observer)

    dev_log_watcher.run_watcher([str(tmp_path)], runtime=0)

    assert producer.flush_calls == 1
    assert observer.stop_calls == 1
    assert observer.join_calls >= 1
    assert observer.scheduled == [str(tmp_path)]
