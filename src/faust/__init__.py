# mypy: ignore-errors
from __future__ import annotations
from typing import Any, Callable

class App:
    class Conf:
        def __init__(self) -> None:
            self.web_enabled: bool = True

    class Topic:
        async def send(self, *, value: bytes) -> None:
            pass

    class Agent:
        def __init__(self, fun: Callable[[Any], Any]) -> None:
            self.fun = fun

    def __init__(self, name: str, broker: str | None = None) -> None:
        self.name = name
        self.broker = broker
        self.conf = self.Conf()
        self.agents: dict[str, App.Agent] = {}

    def topic(self, name: str, value_type: Any | None = None) -> "App.Topic":
        return self.Topic()

    def agent(self, source_topic: "App.Topic") -> Callable[[Callable[[Any], Any]], Callable[[Any], Any]]:
        def decorator(func: Callable[[Any], Any]) -> Callable[[Any], Any]:
            self.agents[func.__name__] = self.Agent(func)
            return func
        return decorator

    def main(self) -> None:
        pass
