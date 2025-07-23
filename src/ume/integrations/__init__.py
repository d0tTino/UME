"""Integrations for external frameworks."""

from .base import AsyncBaseClient, BaseClient, IntegrationError
from .langgraph import LangGraph, AsyncLangGraph
from .letta import Letta, AsyncLetta
from .memgpt import MemGPT, AsyncMemGPT
from .supermemory import SuperMemory, AsyncSuperMemory
from .crewai import CrewAI, AsyncCrewAI
from .autogen import AutoGen, AsyncAutoGen
from .registry import (
    register_adapter,
    get_adapter,
    available_adapters,
    register_builtin_adapters,
)

register_builtin_adapters()

__all__ = [
    "LangGraph",
    "AsyncLangGraph",
    "Letta",
    "AsyncLetta",
    "MemGPT",
    "AsyncMemGPT",
    "CrewAI",
    "AsyncCrewAI",
    "AutoGen",
    "AsyncAutoGen",
    "SuperMemory",
    "AsyncSuperMemory",
    "BaseClient",
    "AsyncBaseClient",
    "IntegrationError",
    "register_adapter",
    "get_adapter",
    "available_adapters",
    "register_builtin_adapters",
]
