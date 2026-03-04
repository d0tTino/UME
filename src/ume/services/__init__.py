"""Utility service functions for UME."""

from __future__ import annotations

from importlib import import_module

__all__ = ["ingest_event", "ingest_events_batch"]


def __getattr__(name: str):
    if name in {"ingest_event", "ingest_events_batch"}:
        module = import_module("ume.services.ingest")
        return getattr(module, name)
    raise AttributeError(name)
