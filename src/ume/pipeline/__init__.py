"""Streaming pipeline utilities."""

try:
    from .privacy_agent import run_privacy_agent
except Exception:  # pragma: no cover - optional dependencies may be missing
    run_privacy_agent = None  # type: ignore[assignment]

try:
    from .stream_processor import build_app
except Exception:  # pragma: no cover - optional dependencies may be missing
    build_app = None  # type: ignore[assignment]

__all__ = ["run_privacy_agent", "build_app"]
