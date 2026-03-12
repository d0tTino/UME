"""Deprecated compatibility wrapper for :mod:`ume.pipeline.stream_processor`."""

from __future__ import annotations

from .deprecations import warn_deprecated
from .pipeline.stream_processor import app, build_app, main

warn_deprecated("ume.stream_processor", stacklevel=2)

__all__ = ["app", "build_app", "main"]
