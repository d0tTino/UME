from ume.policy import can_read_reflections


def test_can_read_reflections_valid_role() -> None:
    assert can_read_reflections("ProjectManager")
    assert can_read_reflections("Viewer")


def test_can_read_reflections_shareable() -> None:
    assert can_read_reflections("Other", shareable=True)


def test_can_read_reflections_forbidden() -> None:
    assert not can_read_reflections("Other")
