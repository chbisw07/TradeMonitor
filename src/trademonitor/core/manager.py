"""Core TradeMonitor runtime coordinator for TM1/TGT1."""

from __future__ import annotations

from collections.abc import Mapping
from threading import RLock
from typing import Any

from trademonitor.core.context import RuntimeContexts
from trademonitor.core.event_bus import EventBus
from trademonitor.domain.events import DomainEvent
from trademonitor.persistence.repository import RuntimeRepository


class CoreTMManager:
    """Coordinate runtime contexts, persistence, and auditable events.

    The Core Manager is intentionally *not* a trading expert. It coordinates
    context ownership and event flow and provides a single controlled mutation
    surface for the TM1 runtime.
    """

    def __init__(self, repository: RuntimeRepository, event_bus: EventBus | None = None) -> None:
        self._repository = repository
        self._event_bus = event_bus or EventBus()
        self._contexts = RuntimeContexts.empty()
        self._lock = RLock()
        self._started = False

    @property
    def contexts(self) -> RuntimeContexts:
        return self._contexts

    @property
    def started(self) -> bool:
        return self._started

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    def start(self) -> None:
        """Initialize persistence and restore the last durable runtime context."""
        with self._lock:
            self._repository.initialize()
            records = self._repository.load_contexts()
            self._contexts = RuntimeContexts.from_records(records) if records else RuntimeContexts.empty()
            self._contexts.get("health").patch(
                {
                    "core": "HEALTHY",
                    "runtime": "STARTED",
                    "live_execution_enabled": False,
                }
            )
            self._persist_all_contexts()
            self._started = True
            self._record_event(
                DomainEvent.create(
                    "CORE_STARTED",
                    source="CORE",
                    payload={"restored_context_count": len(records)},
                )
            )

    def stop(self) -> None:
        """Persist current runtime state and stop the coordinator."""
        with self._lock:
            self._ensure_started()
            self._contexts.get("health").patch({"runtime": "STOPPED"})
            self._persist_all_contexts()
            self._record_event(DomainEvent.create("CORE_STOPPED", source="CORE"))
            self._started = False

    def patch_context(
        self,
        context_name: str,
        values: Mapping[str, Any],
        *,
        source: str,
        reason: str | None = None,
    ) -> None:
        """Apply a controlled context mutation and record it durably."""
        with self._lock:
            self._ensure_started()
            context = self._contexts.get(context_name)
            previous_version = context.version
            context.patch(values)
            self._repository.save_context(context.to_record())
            self._record_event(
                DomainEvent.create(
                    "CONTEXT_UPDATED",
                    source=source,
                    payload={
                        "context": context_name,
                        "previous_version": previous_version,
                        "version": context.version,
                        "changes": dict(values),
                        "reason": reason,
                    },
                )
            )

    def publish(self, event: DomainEvent) -> None:
        """Record an event first, then publish it to runtime subscribers."""
        with self._lock:
            self._ensure_started()
            self._record_event(event)

    def status_snapshot(self) -> dict[str, dict[str, Any]]:
        """Return a user-facing copy of the current runtime contexts."""
        with self._lock:
            return {
                name: {
                    "version": context.version,
                    "updated_at": context.updated_at.isoformat(),
                    "data": dict(context.data),
                }
                for name, context in sorted(self._contexts.contexts.items())
            }

    def _record_event(self, event: DomainEvent) -> None:
        self._repository.append_event(event.to_record())
        self._event_bus.publish(event)

    def _persist_all_contexts(self) -> None:
        for context in self._contexts.contexts.values():
            self._repository.save_context(context.to_record())

    def _ensure_started(self) -> None:
        if not self._started:
            raise RuntimeError("CoreTMManager must be started before use")
