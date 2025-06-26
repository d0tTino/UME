"""Rego policy middleware for event processing."""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import tempfile

from .event import Event
from .graph_adapter import IGraphAdapter


class PolicyEvaluationError(Exception):
    """Raised when the policy evaluation fails."""


class RegoPolicyMiddleware:
    """Middleware that validates events using a Rego policy."""

    def __init__(self, policy_path: str, opa_executable: str = "opa") -> None:
        self.policy_path = policy_path
        self.opa_executable = opa_executable

    def allows(self, event: Event, graph: IGraphAdapter) -> bool:
        """Return True if the policy allows the event."""
        input_data = {
            "event": dataclasses.asdict(event),
            "graph": graph.dump(),
        }
        with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
            json.dump(input_data, tmp)
            tmp_path = tmp.name
        try:
            result = subprocess.run(
                [
                    self.opa_executable,
                    "eval",
                    "-d",
                    self.policy_path,
                    "-i",
                    tmp_path,
                    "data.ume.allow",
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            # Ensure temporary file is removed
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        if result.returncode != 0:
            raise PolicyEvaluationError(
                f"Policy evaluation failed: {result.stderr.strip()}"
            )
        try:
            output = json.loads(result.stdout)
            value = output["result"][0]["expressions"][0]["value"]
        except Exception as exc:  # noqa: BLE001
            raise PolicyEvaluationError(
                f"Invalid policy output: {result.stdout!r}"
            ) from exc
        return bool(value)

