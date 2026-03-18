"""Kernel event ledger compatibility exports."""

from importlib import import_module
from typing import Any


def __getattr__(name: str):
    if name == "EventLedger":
        return import_module("ume.event_ledger").EventLedger
    raise AttributeError(name)


EventLedger: Any

__all__ = ["EventLedger"]
