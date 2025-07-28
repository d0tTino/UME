from ume.policy import (
    can_modify_telemetry,
    can_read_projects,
    can_read_reflections,
)


def test_can_read_reflections_valid_role() -> None:
    assert can_read_reflections("ProjectManager")
    assert can_read_reflections("Viewer")


def test_can_read_reflections_shareable() -> None:
    assert can_read_reflections("Other", shareable=True)


def test_can_read_reflections_forbidden() -> None:
    assert not can_read_reflections("Other")


def test_can_read_projects() -> None:
    assert can_read_projects("ProjectManager")
    assert can_read_projects("Other", shareable=True)
    assert not can_read_projects("Viewer")


def test_can_modify_telemetry() -> None:
    assert can_modify_telemetry("TelemetryAdmin")
    assert not can_modify_telemetry("ProjectManager")
