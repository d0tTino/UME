import pytest

from ume.integrations.registry import (
    INTEGRATION_CAPABILITY,
    register_adapter,
    get_adapter,
    register_builtin_adapters,
)
from ume.integrations.langgraph import LangGraph
from ume.plugins.registry import clear_plugins


class DummyAdapter:
    pass


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    clear_plugins(capability=INTEGRATION_CAPABILITY)
    register_builtin_adapters()


def test_register_and_retrieve() -> None:
    register_adapter("dummy", DummyAdapter)
    assert get_adapter("dummy") is DummyAdapter


def test_builtin_registered() -> None:
    assert get_adapter("langgraph") is LangGraph


def test_register_builtin_function() -> None:
    register_builtin_adapters()
    assert get_adapter("langgraph") is LangGraph
