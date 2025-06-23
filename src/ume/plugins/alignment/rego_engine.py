"""Rego-based alignment plugin."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import AlignmentPlugin, PolicyViolationError, register_plugin
from ...event import Event

try:  # Optional dependency
    from regopy import Interpreter as RegoInterpreter
except Exception:  # pragma: no cover - optional dependency
    RegoInterpreter = None


class RegoPolicyEngine(AlignmentPlugin):
    """Evaluate events against Rego policies."""

    def __init__(self, policy_dir: str | Path, query: str = "data.ume.allow") -> None:
        if RegoInterpreter is None:
            raise ImportError("regopy is required for RegoPolicyEngine")
        self._interp = RegoInterpreter()
        self._query = query
        self._load_policies(Path(policy_dir))

    def _load_policies(self, policy_dir: Path) -> None:
        for path in policy_dir.glob("*.rego"):
            with path.open("r", encoding="utf-8") as f:
                self._interp.add_module(path.name, f.read())

    def validate(self, event: Event) -> None:
        data: dict[str, Any] = event.__dict__
        self._interp.set_input(data)
        output = self._interp.query(self._query)
        allowed = bool(output and output[0].expressions and output[0].expressions[0])
        if not allowed:
            raise PolicyViolationError(f"Event {event.event_id} denied by Rego policy")


# Register plugin automatically if regopy is installed
if RegoInterpreter is not None:
    default_dir = Path(__file__).with_name("policies")
    register_plugin(RegoPolicyEngine(default_dir))
