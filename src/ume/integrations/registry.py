from __future__ import annotations

from typing import Iterable

from ume.plugins.registry import get_plugin_constructor, list_plugins, register_plugin


INTEGRATION_CAPABILITY = "integration_adapter"


def register_adapter(name: str, cls: type) -> None:
    """Register an integration adapter class under ``name``."""
    register_plugin(INTEGRATION_CAPABILITY, name, cls)


def get_adapter(name: str) -> type:
    """Return the adapter class registered under ``name``."""
    return get_plugin_constructor(INTEGRATION_CAPABILITY, name)


def available_adapters() -> Iterable[str]:
    """Return names of all registered adapters."""
    return [item["name"] for item in list_plugins(capability=INTEGRATION_CAPABILITY)]


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
