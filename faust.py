"""Minimal Faust stub for tests."""
from __future__ import annotations
from types import SimpleNamespace
from collections import OrderedDict
from typing import Any, Callable

class Topic:
    def __init__(self, name: str, value_type: Any = None):
        self.name = name
        self.value_type = value_type

    async def send(self, *, value: bytes) -> None:  # pragma: no cover - stub
        pass

class Agent:
    def __init__(self, fun: Callable[[Any], Any], channel: Topic):
        self.fun = fun
        self.channel = channel

class App:
    def __init__(self, name: str, broker: str | None = None):
        self.name = name
        self.broker = broker
        self.conf = SimpleNamespace(web_enabled=True)
        self.agents: dict[str, Agent] = OrderedDict()

    def topic(self, name: str, value_type: Any = None) -> Topic:
        return Topic(name, value_type=value_type)

    def agent(self, channel: Topic):
        def decorator(func: Callable[[Any], Any]) -> Callable[[Any], Any]:
            self.agents[func.__name__] = Agent(func, channel)
            return func
        return decorator

    def main(self) -> None:  # pragma: no cover - stub
        pass
