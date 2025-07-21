from ume.integrations.registry import register_adapter, get_adapter
from ume.integrations.langgraph import LangGraph


class DummyAdapter:
    pass


def test_register_and_retrieve() -> None:
    register_adapter("dummy", DummyAdapter)
    assert get_adapter("dummy") is DummyAdapter


def test_builtin_registered() -> None:
    assert get_adapter("langgraph") is LangGraph
