from .base import BaseEventHandler, HandlerContext


class NoOpEventHandler(BaseEventHandler):
    def apply(self, context: HandlerContext) -> None:
        return None
