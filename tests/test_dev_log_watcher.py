import importlib.util
import json
import sys
import types
from pathlib import Path
import logging
from types import SimpleNamespace
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch

from ume.event import parse_event

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src" / "ume"


def load_dev_log_watcher(monkeypatch: MonkeyPatch):
    ume_pkg = types.ModuleType("ume")
    config_stub = types.ModuleType("ume.config")
    config_stub.settings = SimpleNamespace(
        KAFKA_BOOTSTRAP_SERVERS="localhost:9092",
        KAFKA_RAW_EVENTS_TOPIC="ume-raw-events",
    )
    monkeypatch.setitem(sys.modules, "ume", ume_pkg)
    monkeypatch.setitem(sys.modules, "ume.config", config_stub)
    ume_pkg.config = config_stub

    event_spec = importlib.util.spec_from_file_location("ume.event", SRC_DIR / "event.py")
    event_module = importlib.util.module_from_spec(event_spec)
    assert event_spec.loader is not None
    event_spec.loader.exec_module(event_module)
    ume_pkg.event = event_module
    monkeypatch.setitem(sys.modules, "ume.event", event_module)

    watchers_pkg = types.ModuleType("ume.watchers")
    ume_pkg.watchers = watchers_pkg
    monkeypatch.setitem(sys.modules, "ume.watchers", watchers_pkg)

    confluent = types.ModuleType("confluent_kafka")

    class Producer:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def produce(self, *_: Any, **__: Any) -> None:
            pass

        def flush(self) -> None:  # pragma: no cover - stub
            pass

    class KafkaException(Exception):
        pass

    confluent.Producer = Producer
    confluent.KafkaException = KafkaException
    monkeypatch.setitem(sys.modules, "confluent_kafka", confluent)

    events = types.ModuleType("watchdog.events")

    class FileSystemEvent:
        def __init__(self, src_path: str = "", is_directory: bool = False) -> None:
            self.src_path = src_path
            self.is_directory = is_directory

    class FileSystemEventHandler:
        pass

    events.FileSystemEvent = FileSystemEvent
    events.FileSystemEventHandler = FileSystemEventHandler
    monkeypatch.setitem(sys.modules, "watchdog.events", events)

    observers = types.ModuleType("watchdog.observers")

    class Observer:
        pass

    observers.Observer = Observer
    monkeypatch.setitem(sys.modules, "watchdog.observers", observers)

    devlog_spec = importlib.util.spec_from_file_location(
        "ume.watchers.dev_log_watcher", SRC_DIR / "watchers" / "dev_log_watcher.py"
    )
    dev_log_watcher = importlib.util.module_from_spec(devlog_spec)
    assert devlog_spec.loader is not None
    devlog_spec.loader.exec_module(dev_log_watcher)
    watchers_pkg.dev_log_watcher = dev_log_watcher
    monkeypatch.setitem(sys.modules, "ume.watchers.dev_log_watcher", dev_log_watcher)

    return dev_log_watcher


def test_handler_produces_event(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    dev_log_watcher = load_dev_log_watcher(monkeypatch)
    messages: list[bytes] = []

    class Producer:
        def produce(self, topic: str, data: bytes) -> None:
            messages.append(data)

    handler = dev_log_watcher.DevLogHandler(Producer())

    fake_event: Any = SimpleNamespace(src_path=str(tmp_path / "file.txt"), is_directory=False)

    handler.on_modified(fake_event)

    assert messages
    evt = parse_event(json.loads(messages[0].decode()))
    assert evt.payload["node_id"] == str(tmp_path / "file.txt")


def test_run_watcher_produces_event(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    dev_log_watcher = load_dev_log_watcher(monkeypatch)
    messages: list[bytes] = []

    class Producer:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def produce(self, topic: str, data: bytes) -> None:
            messages.append(data)

        def flush(self) -> None:
            pass

    class DummyObserver:
        def __init__(self) -> None:
            self.scheduled: list[str] = []
            self.handler: dev_log_watcher.DevLogHandler | None = None
            self.join_calls = 0

        def schedule(self, handler: dev_log_watcher.DevLogHandler, path: str, recursive: bool = True) -> None:
            self.scheduled.append(path)
            self.handler = handler

        def start(self) -> None:  # pragma: no cover - noop for tests
            pass

        def join(self) -> None:  # pragma: no cover - simulate event
            if self.join_calls == 0 and self.handler is not None:
                fake_event: Any = SimpleNamespace(
                    src_path=str(tmp_path / "watched.txt"),
                    is_directory=False,
                )
                self.handler.on_modified(fake_event)
            self.join_calls += 1

        def stop(self) -> None:  # pragma: no cover - noop for tests
            pass

    observer = DummyObserver()
    monkeypatch.setattr(dev_log_watcher, "Producer", lambda *_, **__: Producer())
    monkeypatch.setattr(dev_log_watcher, "Observer", lambda: observer)

    dev_log_watcher.run_watcher([str(tmp_path)], runtime=0)

    assert observer.scheduled == [str(tmp_path)]
    assert messages
    evt = parse_event(json.loads(messages[0].decode()))
    assert evt.payload["node_id"].endswith("watched.txt")


def test_run_watcher_interrupt_stops_and_flushes(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    dev_log_watcher = load_dev_log_watcher(monkeypatch)

    class Producer:
        def __init__(self, *_: Any, **__: Any) -> None:
            self.flush_calls = 0

        def produce(self, topic: str, data: bytes) -> None:  # pragma: no cover - not used
            pass

        def flush(self) -> None:
            self.flush_calls += 1

    class DummyObserver:
        def __init__(self) -> None:
            self.stop_calls = 0
            self.join_calls = 0
            self.handler: dev_log_watcher.DevLogHandler | None = None

        def schedule(self, handler: dev_log_watcher.DevLogHandler, path: str, recursive: bool = True) -> None:
            self.handler = handler

        def start(self) -> None:  # pragma: no cover - noop for tests
            pass

        def join(self) -> None:  # pragma: no cover - simulate interrupt
            self.join_calls += 1
            if self.join_calls == 1:
                raise KeyboardInterrupt

        def stop(self) -> None:  # pragma: no cover - track stop call
            self.stop_calls += 1

    producer = Producer()
    observer = DummyObserver()
    monkeypatch.setattr(dev_log_watcher, "Producer", lambda *_, **__: producer)
    monkeypatch.setattr(dev_log_watcher, "Observer", lambda: observer)

    with pytest.raises(KeyboardInterrupt):
        dev_log_watcher.run_watcher([str(tmp_path)])

    assert producer.flush_calls == 1
    assert observer.stop_calls == 1
    assert observer.join_calls == 2


def test_run_watcher_skips_missing_path(tmp_path: Path, monkeypatch: MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    dev_log_watcher = load_dev_log_watcher(monkeypatch)

    class Producer:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def produce(self, topic: str, data: bytes) -> None:  # pragma: no cover - not used
            pass

        def flush(self) -> None:  # pragma: no cover - noop
            pass

    class DummyObserver:
        def __init__(self) -> None:
            self.scheduled: list[str] = []

        def schedule(self, handler: dev_log_watcher.DevLogHandler, path: str, recursive: bool = True) -> None:
            self.scheduled.append(path)

        def start(self) -> None:  # pragma: no cover - noop for tests
            pass

        def join(self) -> None:  # pragma: no cover - noop
            pass

        def stop(self) -> None:  # pragma: no cover - noop
            pass

    observer = DummyObserver()
    monkeypatch.setattr(dev_log_watcher, "Producer", lambda *_, **__: Producer())
    monkeypatch.setattr(dev_log_watcher, "Observer", lambda: observer)

    missing = tmp_path / "missing"
    caplog.set_level(logging.WARNING)
    dev_log_watcher.run_watcher([str(missing), str(tmp_path)], runtime=0)

    assert observer.scheduled == [str(tmp_path)]
    assert any("does not exist" in rec.message for rec in caplog.records)


def test_run_watcher_no_valid_paths(tmp_path: Path, monkeypatch: MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    dev_log_watcher = load_dev_log_watcher(monkeypatch)

    class Producer:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def produce(self, topic: str, data: bytes) -> None:  # pragma: no cover - not used
            pass

        def flush(self) -> None:  # pragma: no cover - noop
            pass

    class DummyObserver:
        def __init__(self) -> None:
            self.started = False

        def schedule(self, handler: dev_log_watcher.DevLogHandler, path: str, recursive: bool = True) -> None:
            pass

        def start(self) -> None:  # pragma: no cover - should not be called
            self.started = True

        def join(self) -> None:  # pragma: no cover - noop
            pass

        def stop(self) -> None:  # pragma: no cover - noop
            pass

    observer = DummyObserver()
    monkeypatch.setattr(dev_log_watcher, "Producer", lambda *_, **__: Producer())
    monkeypatch.setattr(dev_log_watcher, "Observer", lambda: observer)

    missing = tmp_path / "missing"
    caplog.set_level(logging.WARNING)
    dev_log_watcher.run_watcher([str(missing)], runtime=0)

    assert not observer.started
    assert any("No existing paths" in rec.message for rec in caplog.records)
