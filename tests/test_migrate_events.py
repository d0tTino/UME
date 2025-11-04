from __future__ import annotations

from ume.migrate_events import TARGET_VERSION, _migrate_event


def test_migrate_event_removes_deprecated_edges() -> None:
    """Events targeting deprecated edge labels should be dropped."""

    event = {"event_type": "CREATE_EDGE", "label": "REMEMBERS"}

    assert _migrate_event(event) is None

    legacy_short = {"event_type": "CREATE_EDGE", "label": "L"}

    assert _migrate_event(legacy_short) is None


def test_migrate_event_remaps_new_label() -> None:
    """Legacy NEW_LABEL edges migrate to TAGGED_AS with schema metadata."""

    event = {"event_type": "CREATE_EDGE", "label": "NEW_LABEL", "payload": {}}

    migrated = _migrate_event(event)
    assert migrated is not None
    assert migrated["label"] == "TAGGED_AS"
    attrs = migrated["payload"]["attributes"]
    assert attrs == {"schema_version": TARGET_VERSION}


def test_migrate_event_converts_has_permission_editor() -> None:
    """HAS_PERMISSION edges retain custom attributes when mapped to OWNED_BY."""

    event = {
        "event_type": "CREATE_EDGE",
        "label": "HAS_PERMISSION",
        "payload": {"attributes": {"permission_level": "editor", "note": "custom"}},
    }

    migrated = _migrate_event(event)
    assert migrated is not None
    assert migrated["label"] == "OWNED_BY"
    attrs = migrated["payload"]["attributes"]
    assert attrs["permission_level"] == "editor"
    assert attrs["note"] == "custom"
    assert attrs["schema_version"] == TARGET_VERSION


def test_migrate_event_converts_has_permission_default_viewer() -> None:
    """HAS_PERMISSION edges without metadata fall back to viewer SHARED_WITH."""

    event = {"event_type": "CREATE_EDGE", "label": "HAS_PERMISSION", "payload": {}}

    migrated = _migrate_event(event)
    assert migrated is not None
    assert migrated["label"] == "SHARED_WITH"
    attrs = migrated["payload"]["attributes"]
    assert attrs["permission_level"] == "viewer"
    assert attrs["schema_version"] == TARGET_VERSION


def test_migrate_delete_event_updates_label_only() -> None:
    """Delete events with HAS_PERMISSION should map their label to SHARED_WITH by default."""

    event = {"event_type": "DELETE_EDGE", "label": "HAS_PERMISSION"}

    migrated = _migrate_event(event)
    assert migrated is not None
    assert migrated["label"] == "SHARED_WITH"
