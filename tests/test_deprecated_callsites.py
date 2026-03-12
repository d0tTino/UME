from scripts.check_deprecated_callsites import find_violations


def test_no_new_deprecated_callsites() -> None:
    assert find_violations() == []
