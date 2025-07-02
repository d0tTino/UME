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
