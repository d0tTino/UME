"""Simple multi-tier memory manager."""

from __future__ import annotations

from collections import deque
from typing import Deque, List, Optional

from .event import Event


class MemoryManager:
    """Manage events across short-term, long-term, and archive storage."""

    def __init__(self, short_term_limit: int = 100, long_term_limit: int = 1000) -> None:
        self.short_term_limit = short_term_limit
        self.long_term_limit = long_term_limit
        self._short_term: Deque[Event] = deque()
        self._long_term: List[Event] = []
        self._archive: List[Event] = []

    # Properties for inspection in tests
    @property
    def short_term(self) -> List[Event]:
        return list(self._short_term)

    @property
    def long_term(self) -> List[Event]:
        return list(self._long_term)

    @property
    def archive(self) -> List[Event]:
        return list(self._archive)

    def insert_event(self, event: Event) -> None:
        """Insert a new event and perform aging between tiers."""
        self._short_term.append(event)

        if len(self._short_term) > self.short_term_limit:
            moved = self._short_term.popleft()
            self._long_term.append(moved)

        if len(self._long_term) > self.long_term_limit:
            archived = self._long_term.pop(0)
            self._archive.append(archived)

    def get_event(self, event_id: str) -> Optional[Event]:
        """Retrieve an event from any tier by its ID."""
        for event in reversed(self._short_term):
            if event.event_id == event_id:
                return event
        for event in self._long_term:
            if event.event_id == event_id:
                return event
        for event in self._archive:
            if event.event_id == event_id:
                return event
        return None
