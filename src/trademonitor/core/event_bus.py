"""Small synchronous event bus used by the TM1 coordinating core.

The bus is intentionally synchronous in TM1/TGT1. It creates an explicit event
boundary without prematurely committing the architecture to threads/processes.
Concurrency can be introduced later behind the same publication contract.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from threading import RLock

from trademonitor.domain.events import DomainEvent

EventHandler = Callable[[DomainEvent], None]


class EventBus:
    """Thread-safe registration and synchronous event publication."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard_handlers: list[EventHandler] = []
        self._lock = RLock()

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        with self._lock:
            if handler not in self._handlers[event_name]:
                self._handlers[event_name].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        with self._lock:
            if handler not in self._wildcard_handlers:
                self._wildcard_handlers.append(handler)

    def publish(self, event: DomainEvent) -> None:
        with self._lock:
            handlers = tuple(self._handlers.get(event.name, ()))
            wildcard_handlers = tuple(self._wildcard_handlers)
        for handler in (*handlers, *wildcard_handlers):
            handler(event)
