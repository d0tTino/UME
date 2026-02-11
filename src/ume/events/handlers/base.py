from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ...event import Event
from ...graph_adapter import IGraphAdapter


@dataclass(frozen=True)
class HandlerContext:
    event: Event
    graph: IGraphAdapter
    schema_version: str


@runtime_checkable
class EventHandler(Protocol):
    def validate(self, context: HandlerContext) -> None: ...

    def apply(self, context: HandlerContext) -> None: ...

    def emit_listeners(self, context: HandlerContext) -> None: ...


class BaseEventHandler:
    def validate(self, context: HandlerContext) -> None:
        return None

    def apply(self, context: HandlerContext) -> None:
        raise NotImplementedError

    def emit_listeners(self, context: HandlerContext) -> None:
        return None

    def handle(self, context: HandlerContext) -> None:
        self.validate(context)
        self.apply(context)
        self.emit_listeners(context)
