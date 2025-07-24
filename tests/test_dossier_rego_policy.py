import re
from pathlib import Path
import pytest

pytest.importorskip("regopy")
from regopy import Interpreter  # type: ignore


def _load_policy() -> str:
    text = Path("docs/ACCESS_CONTROL.md").read_text()
    m = re.search(r"```rego\n(.*?)```", text, re.S)
    assert m, "Rego policy snippet not found"
    return m.group(1)


def _eval(interp: Interpreter, rule: str, **data: object) -> bool:
    interp.set_input(data)
    out = interp.query(f"data.ume.dossier.{rule}")
    return bool(out.results and out.results[0].expressions and out.results[0].expressions[0])


def test_access_control_rego() -> None:
    policy = _load_policy()
    interp = Interpreter()
    interp.add_module("dossier.rego", policy)

    assert _eval(interp, "can_read_projects", role="ProjectManager", metadata={"shareable": False})
    assert _eval(interp, "can_read_projects", role="Viewer", metadata={"shareable": False})
    assert _eval(interp, "can_read_projects", role="Other", metadata={"shareable": True})
    assert not _eval(interp, "can_read_projects", role="Other", metadata={"shareable": False})

    assert _eval(interp, "allow_add_project", role="ProjectManager")
    assert not _eval(interp, "allow_add_project", role="Viewer")

    assert _eval(interp, "can_modify_telemetry", role="TelemetryAdmin")
    assert not _eval(interp, "can_modify_telemetry", role="ProjectManager")
