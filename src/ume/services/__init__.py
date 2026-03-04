"""Utility service functions for UME."""

from __future__ import annotations

from importlib import import_module

__all__ = ["ingest_event", "ingest_events_batch", "EventProcessorService", "DEFAULT_EVENT_PROCESSOR"]


def __getattr__(name: str):
    if name in {"ingest_event", "ingest_events_batch"}:
        module = import_module("ume.services.ingest")
        return getattr(module, name)
    if name in {"EventProcessorService", "DEFAULT_EVENT_PROCESSOR"}:
        module = import_module("ume.services.event_processor")
        return getattr(module, name)
    raise AttributeError(name)
