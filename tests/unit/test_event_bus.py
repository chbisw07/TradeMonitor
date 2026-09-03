"""Tests for the explicit event publication boundary."""

from trademonitor.core.event_bus import EventBus
from trademonitor.domain.events import DomainEvent


def test_event_bus_publishes_named_and_wildcard_handlers() -> None:
    bus = EventBus()
    seen: list[str] = []
    bus.subscribe("PRICE", lambda event: seen.append(f"named:{event.name}"))
    bus.subscribe_all(lambda event: seen.append(f"all:{event.name}"))

    bus.publish(DomainEvent.create("PRICE", source="TEST"))

    assert seen == ["named:PRICE", "all:PRICE"]
