"""Backward compatibility wrapper for :mod:`ume.pipeline.privacy_agent`."""
from __future__ import annotations

from .pipeline.privacy_agent import *  # noqa: F401,F403
from .pipeline.privacy_agent import run_privacy_agent

if __name__ == "__main__":  # pragma: no cover - manual execution
    run_privacy_agent()
