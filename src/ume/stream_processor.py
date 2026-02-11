"""Deprecated compatibility wrapper for :mod:`ume.pipeline.stream_processor`."""

from __future__ import annotations

from .pipeline.stream_processor import app, build_app, main

__all__ = ["app", "build_app", "main"]
