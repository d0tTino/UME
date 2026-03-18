from pathlib import Path

from scripts.check_deprecated_callsites import find_violations


def test_no_new_deprecated_callsites() -> None:
    assert find_violations() == []


def test_detects_new_top_level_compat_import(tmp_path: Path) -> None:
    sample = tmp_path / "src" / "demo.py"
    sample.parent.mkdir(parents=True)
    sample.write_text("from ume import MockGraph\n", encoding="utf-8")

    assert find_violations(tmp_path) == [
        "src/demo.py:1: deprecated callsite for ume.MockGraph"
    ]
