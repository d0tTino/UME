import json
from types import SimpleNamespace
from typing import Any
from pathlib import Path
from _pytest.monkeypatch import MonkeyPatch

from ume.watchers import dev_log_watcher
from ume.watchers.dev_log_watcher import DevLogHandler
from ume.event import parse_event


def test_handler_produces_event(tmp_path: Path) -> None:
    messages: list[bytes] = []

    class Producer:
        def produce(self, topic: str, data: bytes) -> None:
            messages.append(data)

    handler = DevLogHandler(Producer())

    fake_event: Any = SimpleNamespace(src_path=str(tmp_path / "file.txt"), is_directory=False)

    handler.on_modified(fake_event)

    assert messages
    evt = parse_event(json.loads(messages[0].decode()))
    assert evt.payload["node_id"] == str(tmp_path / "file.txt")


def test_run_watcher_produces_event(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    messages: list[bytes] = []

    class Producer:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def produce(self, topic: str, data: bytes) -> None:
            messages.append(data)

    class DummyObserver:
        def __init__(self) -> None:
            self.scheduled: list[str] = []
            self.handler: DevLogHandler | None = None
            self.join_calls = 0

        def schedule(
            self, handler: DevLogHandler, path: str, recursive: bool = True
        ) -> None:
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

    dev_log_watcher.run_watcher([str(tmp_path)])

    assert observer.scheduled == [str(tmp_path)]
    assert messages
    evt = parse_event(json.loads(messages[0].decode()))
    assert evt.payload["node_id"].endswith("watched.txt")
