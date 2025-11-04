import itertools
from typing import Iterable

import pytest

from ume import migrate_events


ISO_TS = "2024-01-01T00:00:00Z"


def _legacy_edge(label: str, target: str, permission: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {}
    if permission is not None:
        payload = {"attributes": {"permission_level": permission}}
    return {
        "eventType": "CREATE_EDGE",
        "timestamp": ISO_TS,
        "node_id": "doc",
        "target_node_id": target,
        "label": label,
        "payload": payload,
    }


def test_migrate_events_ledger_path(monkeypatch: pytest.MonkeyPatch) -> None:
    ledger_events = [
        _legacy_edge("HAS_PERMISSION", "user_editor", "editor"),
        _legacy_edge("HAS_PERMISSION", "user_viewer", "viewer"),
        _legacy_edge("REMEMBERS", "user_ignore"),
    ]

    def fake_iter_ledger(_ledger: object) -> Iterable[dict[str, object]]:
        return iter(itertools.chain(ledger_events))

    monkeypatch.setattr(migrate_events, "_iter_ledger_events", fake_iter_ledger)

    envelopes = list(migrate_events.migrate_events("ledger"))

    assert [env["schema_version"] for env in envelopes] == ["3.0.0", "3.0.0"]

    owned, shared = [env["event"] for env in envelopes]
    assert owned["label"] == "OWNED_BY"
    assert owned["payload"]["attributes"]["permission_level"] == "editor"
    assert shared["label"] == "SHARED_WITH"
    assert shared["payload"]["attributes"]["permission_level"] == "viewer"


def test_migrate_events_kafka_envelopes(monkeypatch: pytest.MonkeyPatch) -> None:
    kafka_messages = [
        {"event": _legacy_edge("HAS_PERMISSION", "user_default")},
        {"event": _legacy_edge("LINKS_TO", "other")},
    ]

    def fake_iter_kafka() -> Iterable[dict[str, object]]:
        return iter(kafka_messages)

    monkeypatch.setattr(migrate_events, "_iter_kafka_events", fake_iter_kafka)

    envelopes = list(migrate_events.migrate_events("kafka"))

    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope["schema_version"] == "3.0.0"
    event = envelope["event"]
    assert event["label"] == "SHARED_WITH"
    attrs = event["payload"]["attributes"]
    assert attrs["permission_level"] == "viewer"
