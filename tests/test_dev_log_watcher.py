from watchdog.events import FileModifiedEvent
import json

from ume.watchers.dev_log_watcher import DevLogHandler
from ume.event import parse_event


def test_handler_produces_event(tmp_path) -> None:
    messages: list[bytes] = []

    class Producer:
        def produce(self, topic: str, data: bytes) -> None:
            messages.append(data)

    handler = DevLogHandler(Producer())

    fake_event = SimpleNamespace(src_path=str(tmp_path / "file.txt"), is_directory=False)

    handler.on_modified(fake_event)

    assert messages
    evt = parse_event(json.loads(messages[0].decode()))
    assert evt.payload["node_id"] == str(tmp_path / "file.txt")
