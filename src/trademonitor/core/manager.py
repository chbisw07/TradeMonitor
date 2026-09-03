"""Core TradeMonitor runtime coordinator for TM1."""

from __future__ import annotations

from collections.abc import Mapping
from threading import RLock
from typing import Any

from trademonitor.brokers.base import Broker
from trademonitor.core.context import RuntimeContexts
from trademonitor.core.event_bus import EventBus
from trademonitor.domain.events import DomainEvent
from trademonitor.domain.models import PositionRecord
from trademonitor.persistence.repository import RuntimeRepository
from trademonitor.positions.manager import PositionManager


class CoreTMManager:
    """Coordinate runtime contexts, persistence, events, and broker reconciliation.

    The Core Manager is intentionally not a trading expert. It synchronizes
    contexts and delegates broker-position semantics to the Position domain.
    """

    def __init__(self, repository: RuntimeRepository, event_bus: EventBus | None = None) -> None:
        self._repository = repository
        self._event_bus = event_bus or EventBus()
        self._contexts = RuntimeContexts.empty()
        self._positions = PositionManager(repository)
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
            self._contexts.get("broker").data.setdefault("status", "NOT_RECONCILED")
            self._refresh_position_context()
            self._persist_all_contexts()
            self._started = True
            self._record_event(
                DomainEvent.create(
                    "CORE_STARTED",
                    source="CORE",
                    payload={
                        "restored_context_count": len(records),
                        "restored_position_count": len(self._repository.list_positions()),
                    },
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

    def reconcile_broker_truth(self, broker: Broker) -> list[PositionRecord]:
        """Read one coherent broker snapshot and reconcile canonical positions.

        This is strictly read-only with respect to the broker. No order placement,
        modification, cancellation, or adoption occurs in TM1/TGT2.
        """
        with self._lock:
            self._ensure_started()
            snapshot = broker.fetch_account_snapshot()
            if snapshot.broker != broker.name:
                raise ValueError(
                    f"Broker snapshot identity mismatch: adapter={broker.name!r}, "
                    f"snapshot={snapshot.broker!r}"
                )

            positions, events = self._positions.reconcile(snapshot)
            for event in events:
                self._record_event(event)

            broker_values: dict[str, Any] = {
                "status": "RECONCILED",
                "broker": snapshot.broker,
                "observed_at": snapshot.observed_at.isoformat(),
                "position_count": len([p for p in positions if p.is_open]),
                "order_count": snapshot.order_count,
                "fill_count": snapshot.fill_count,
                "read_only": True,
            }
            if snapshot.funds is not None:
                broker_values["funds"] = {
                    "available_cash": self._string_or_none(snapshot.funds.available_cash),
                    "used_margin": self._string_or_none(snapshot.funds.used_margin),
                    "net_value": self._string_or_none(snapshot.funds.net_value),
                }
            self.patch_context(
                "broker",
                broker_values,
                source="BROKER",
                reason="broker truth reconciliation",
            )
            self._refresh_position_context(source="POSITION")
            self._record_event(
                DomainEvent.create(
                    "BROKER_RECONCILED",
                    source="BROKER",
                    payload={
                        "broker": snapshot.broker,
                        "open_position_count": len([p for p in positions if p.is_open]),
                        "managed_open_count": len([p for p in positions if p.is_open and p.is_managed]),
                        "unmanaged_open_count": len(
                            [p for p in positions if p.is_open and not p.is_managed]
                        ),
                    },
                    occurred_at=snapshot.observed_at,
                )
            )
            return positions

    def positions_snapshot(self, *, open_only: bool = False) -> list[PositionRecord]:
        with self._lock:
            self._ensure_started()
            return self._positions.list_positions(open_only=open_only)

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

    def _refresh_position_context(self, *, source: str | None = None) -> None:
        positions = self._repository.list_positions()
        open_positions = [position for position in positions if position.is_open]
        data = {
            "total_known": len(positions),
            "open": len(open_positions),
            "closed": len(positions) - len(open_positions),
            "managed_open": len([p for p in open_positions if p.is_managed]),
            "unmanaged_open": len([p for p in open_positions if not p.is_managed]),
        }
        context = self._contexts.get("position")
        if context.data != data:
            previous_version = context.version
            context.replace(data)
            self._repository.save_context(context.to_record())
            if self._started and source is not None:
                self._record_event(
                    DomainEvent.create(
                        "CONTEXT_UPDATED",
                        source=source,
                        payload={
                            "context": "position",
                            "previous_version": previous_version,
                            "version": context.version,
                            "changes": data,
                            "reason": "position reconciliation summary",
                        },
                    )
                )

    @staticmethod
    def _string_or_none(value: Any) -> str | None:
        return None if value is None else str(value)

    def _ensure_started(self) -> None:
        if not self._started:
            raise RuntimeError("CoreTMManager must be started before use")
