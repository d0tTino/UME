"""Streaming pipeline utilities."""

from typing import Callable, Optional

try:
    from .privacy_agent import run_privacy_agent as _run_privacy_agent
except Exception:  # pragma: no cover - optional dependencies may be missing
    _run_privacy_agent = None

try:
    from .stream_processor import build_app as _build_app
except Exception:  # pragma: no cover - optional dependencies may be missing
    _build_app = None

run_privacy_agent: Optional[Callable[[], None]] = _run_privacy_agent
build_app: Optional[Callable[..., object]] = _build_app

__all__ = ["run_privacy_agent", "build_app"]
