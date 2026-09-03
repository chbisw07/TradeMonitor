"""Core TradeMonitor runtime coordinator for TM1."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from threading import RLock
from typing import Any

from trademonitor.brokers.base import Broker
from trademonitor.core.attention import create_attention_item, resolve_attention_item
from trademonitor.core.context import RuntimeContexts
from trademonitor.core.event_bus import EventBus
from trademonitor.core.health import DomainHealthReport, FaultReport
from trademonitor.domain.enums import AttentionLevel, AttentionStatus, HealthStatus
from trademonitor.domain.events import DomainEvent
from trademonitor.domain.models import AttentionItem, PositionRecord
from trademonitor.persistence.repository import RuntimeRepository
from trademonitor.positions.manager import PositionManager


class CoreTMManager:
    """Coordinate runtime contexts, persistence, health, and broker truth.

    The Core Manager is intentionally not a trading expert. Specialist domains
    own specialist meaning and failures; Core coordinates their summarized state
    into one coherent operating picture.
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

            health = self._contexts.get("health")
            domains = dict(health.data.get("domains", {}))
            domains["CORE"] = DomainHealthReport.create(
                "CORE", HealthStatus.HEALTHY, "Core runtime coordinator is operational"
            ).to_payload()
            health.patch(
                {
                    "core": "HEALTHY",  # retained for TGT1/TGT2 compatibility
                    "runtime": "STARTED",
                    "execution_mode": "PAPER",
                    "live_execution_enabled": False,
                    "domains": domains,
                }
            )
            self._contexts.get("broker").data.setdefault("status", "NOT_RECONCILED")
            self._contexts.get("decision").data.setdefault("attention_queue", [])
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
                        "execution_mode": "PAPER",
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

    # ------------------------------------------------------------------
    # TM1/TGT3 health/fault coordination
    # ------------------------------------------------------------------
    def report_domain_health(self, report: DomainHealthReport) -> None:
        """Accept a summarized health report from a horizontal peer domain."""
        with self._lock:
            self._ensure_started()
            health = self._contexts.get("health")
            domains = dict(health.data.get("domains", {}))
            domains[report.domain] = report.to_payload()
            previous_version = health.version
            health.patch({"domains": domains})
            self._repository.save_context(health.to_record())
            self._record_event(
                DomainEvent.create(
                    "DOMAIN_HEALTH_REPORTED",
                    source=report.domain,
                    payload={
                        **report.to_payload(),
                        "health_context_previous_version": previous_version,
                        "health_context_version": health.version,
                    },
                )
            )

    def report_fault(self, fault: FaultReport) -> None:
        """Record vertical local handling/escalation in domain language.

        A child/component reports first to its immediate competent owner. If the
        owner cannot safely resolve the fault, the report may name the next parent
        (`escalate_to`). Core receives the summarized result, not arbitrary shared
        state mutation from the child.
        """
        with self._lock:
            self._ensure_started()
            event_name = (
                "DOMAIN_FAULT_CONTAINED" if fault.resolved_locally else "DOMAIN_FAULT_ESCALATED"
            )
            payload = {
                "component": fault.component,
                "owner_domain": fault.owner_domain,
                "summary": fault.summary,
                "local_action": fault.local_action,
                "resolved_locally": fault.resolved_locally,
                "impact": list(fault.impact),
                "escalate_to": fault.escalate_to,
            }
            self._record_event(DomainEvent.create(event_name, source=fault.owner_domain, payload=payload))

            if not fault.resolved_locally:
                self.report_domain_health(
                    DomainHealthReport.create(
                        fault.owner_domain,
                        HealthStatus.DEGRADED,
                        fault.summary,
                        impact=fault.impact,
                        parent=fault.escalate_to,
                        escalated_from=fault.component,
                    )
                )

    def add_attention(
        self,
        *,
        level: AttentionLevel | str,
        source: str,
        title: str,
        detail: str,
    ) -> AttentionItem:
        """Add a durable operator-facing item to the Attention queue."""
        with self._lock:
            self._ensure_started()
            item = create_attention_item(level=level, source=source, title=title, detail=detail)
            self._save_attention(item)
            self._record_event(
                DomainEvent.create("ATTENTION_OPENED", source=item.source, payload=item.to_record())
            )
            return item

    def resolve_attention(self, attention_id: str, *, source: str = "CORE") -> AttentionItem:
        with self._lock:
            self._ensure_started()
            items = self.attention_snapshot(active_only=False)
            try:
                current = next(item for item in items if item.attention_id == attention_id)
            except StopIteration as exc:
                raise KeyError(f"Unknown attention item: {attention_id}") from exc
            resolved = resolve_attention_item(current)
            queue = [resolved if item.attention_id == attention_id else item for item in items]
            self._replace_attention_queue(queue)
            self._record_event(
                DomainEvent.create("ATTENTION_RESOLVED", source=source, payload=resolved.to_record())
            )
            return resolved

    def attention_snapshot(self, *, active_only: bool = True) -> list[AttentionItem]:
        with self._lock:
            self._ensure_started()
            raw = self._contexts.get("decision").data.get("attention_queue", [])
            items = [AttentionItem.from_record(record) for record in raw]
            if active_only:
                items = [item for item in items if item.status == AttentionStatus.OPEN.value]
            return sorted(items, key=lambda item: item.created_at)

    # ------------------------------------------------------------------
    # Broker truth reconciliation
    # ------------------------------------------------------------------
    def reconcile_broker_truth(self, broker: Broker) -> list[PositionRecord]:
        """Read one coherent broker snapshot and reconcile canonical positions.

        This remains strictly read-only with respect to the broker. TGT3 adds
        domain health/attention behavior around failures but no broker write path.
        """
        with self._lock:
            self._ensure_started()
            try:
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
                    "broker", broker_values, source="BROKER", reason="broker truth reconciliation"
                )
                self._refresh_position_context(source="POSITION")
                self.report_domain_health(
                    DomainHealthReport.create(
                        "BROKER",
                        HealthStatus.HEALTHY,
                        "Broker truth reconciled successfully",
                        capabilities={"broker_reads": "AVAILABLE", "broker_writes": "DISABLED"},
                    )
                )
                self.report_domain_health(
                    DomainHealthReport.create(
                        "POSITION",
                        HealthStatus.HEALTHY,
                        "Position context reconciled to broker truth",
                    )
                )
                self._record_event(
                    DomainEvent.create(
                        "BROKER_RECONCILED",
                        source="BROKER",
                        payload={
                            "broker": snapshot.broker,
                            "open_position_count": len([p for p in positions if p.is_open]),
                            "managed_open_count": len(
                                [p for p in positions if p.is_open and p.is_managed]
                            ),
                            "unmanaged_open_count": len(
                                [p for p in positions if p.is_open and not p.is_managed]
                            ),
                        },
                        occurred_at=snapshot.observed_at,
                    )
                )
                return positions
            except Exception as exc:
                # The Broker domain owns the failure. It reports summarized impact;
                # unrelated domains are not collapsed by this failure.
                self.patch_context(
                    "broker",
                    {"status": "UNAVAILABLE", "read_only": True},
                    source="BROKER",
                    reason="broker reconciliation failed",
                )
                self.report_fault(
                    FaultReport.create(
                        component=broker.name,
                        owner_domain="BROKER",
                        summary="Broker truth could not be reconciled",
                        local_action="Suspend broker-dependent actions and preserve last known state",
                        resolved_locally=False,
                        impact=("broker truth is stale", "new broker-dependent actions unavailable"),
                        escalate_to="CORE",
                    )
                )
                self.add_attention(
                    level=AttentionLevel.CRITICAL,
                    source="BROKER",
                    title="Broker reconciliation unavailable",
                    detail="New broker-dependent actions are unavailable until broker truth is restored.",
                )
                self._record_event(
                    DomainEvent.create(
                        "BROKER_RECONCILIATION_FAILED",
                        source="BROKER",
                        payload={"broker": broker.name, "error_type": type(exc).__name__},
                    )
                )
                raise

    def events_snapshot(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        """Return durable audit events for diagnostics/tests/control-plane use."""
        with self._lock:
            self._ensure_started()
            return self._repository.list_events(limit=limit)

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

    def control_room_snapshot(self) -> dict[str, Any]:
        """One coherent operator snapshot; Console remains a pure renderer."""
        with self._lock:
            self._ensure_started()
            return {
                "contexts": self.status_snapshot(),
                "positions": self.positions_snapshot(open_only=True),
                "attention": self.attention_snapshot(active_only=True),
            }

    def _save_attention(self, item: AttentionItem) -> None:
        items = self.attention_snapshot(active_only=False)
        items.append(item)
        self._replace_attention_queue(items)

    def _replace_attention_queue(self, items: Sequence[AttentionItem]) -> None:
        context = self._contexts.get("decision")
        previous_version = context.version
        data = dict(context.data)
        data["attention_queue"] = [item.to_record() for item in items]
        context.replace(data)
        self._repository.save_context(context.to_record())
        self._record_event(
            DomainEvent.create(
                "CONTEXT_UPDATED",
                source="ATTENTION",
                payload={
                    "context": "decision",
                    "previous_version": previous_version,
                    "version": context.version,
                    "reason": "attention queue updated",
                },
            )
        )

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
