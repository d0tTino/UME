from __future__ import annotations

from typing import Dict, Iterable

_ADAPTERS: Dict[str, type] = {}


def register_adapter(name: str, cls: type) -> None:
    """Register an integration adapter class under ``name``."""
    _ADAPTERS[name.lower()] = cls


def get_adapter(name: str) -> type:
    """Return the adapter class registered under ``name``."""
    key = name.lower()
    if key not in _ADAPTERS:
        raise ValueError(f"Unknown integration adapter: {name}")
    return _ADAPTERS[key]


def available_adapters() -> Iterable[str]:
    """Return names of all registered adapters."""
    return list(_ADAPTERS.keys())


def register_builtin_adapters() -> None:
    """Register adapters for built-in integrations."""
    from .langgraph import LangGraph
    from .letta import Letta
    from .memgpt import MemGPT
    from .supermemory import SuperMemory
    from .crewai import CrewAI
    from .autogen import AutoGen

    register_adapter("langgraph", LangGraph)
    register_adapter("letta", Letta)
    register_adapter("memgpt", MemGPT)
    register_adapter("supermemory", SuperMemory)
    register_adapter("crewai", CrewAI)
    register_adapter("autogen", AutoGen)
