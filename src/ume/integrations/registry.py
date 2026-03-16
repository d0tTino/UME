from __future__ import annotations

from typing import Iterable, cast

from ume.plugins.registry import (
    ConstructorMetadata,
    get_plugin_constructor,
    get_plugin_metadata,
    list_plugins,
    register_plugin,
)

from ume.capability_schema import build_capability_schema


INTEGRATION_CAPABILITY = "integration_adapter"


def register_adapter(
    name: str,
    cls: type,
    *,
    capabilities: set[str] | frozenset[str] | None = None,
) -> None:
    """Register an integration adapter class under ``name``."""
    if capabilities is None:
        raise ValueError(f"Integration adapter '{name}' must declare capabilities")
    declared = frozenset(capabilities)
    register_plugin(
        INTEGRATION_CAPABILITY,
        name,
        cls,
        metadata=ConstructorMetadata(
            capabilities=declared,
            details={
                "capability_schema": build_capability_schema(
                    domain="integration",
                    backend=name,
                    declared=declared,
                ).as_dict()
            },
        ),
    )


def get_adapter(name: str) -> type:
    """Return the adapter class registered under ``name``."""
    return cast(type, get_plugin_constructor(INTEGRATION_CAPABILITY, name))


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

    register_adapter("langgraph", LangGraph, capabilities={"workflow_orchestration"})
    register_adapter("letta", Letta, capabilities={"agent_memory_sync"})
    register_adapter("memgpt", MemGPT, capabilities={"agent_memory_sync"})
    register_adapter("supermemory", SuperMemory, capabilities={"memory_indexing"})
    register_adapter("crewai", CrewAI, capabilities={"multi_agent_orchestration"})
    register_adapter("autogen", AutoGen, capabilities={"multi_agent_orchestration"})


def get_adapter_capabilities(name: str) -> frozenset[str]:
    """Return declared capabilities for an integration adapter."""
    metadata = get_plugin_metadata(INTEGRATION_CAPABILITY, name)
    return metadata.capabilities
