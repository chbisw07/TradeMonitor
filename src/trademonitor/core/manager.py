"""Core TradeMonitor runtime coordinator for TM1."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from threading import RLock
from typing import Any

from trademonitor.agents.gateway import AgentGateway
from trademonitor.brokers.base import Broker
from trademonitor.candidates.manager import TradeIntakeManager
from trademonitor.core.attention import create_attention_item, resolve_attention_item
from trademonitor.core.context import RuntimeContexts
from trademonitor.core.event_bus import EventBus
from trademonitor.core.health import DomainHealthReport, FaultReport
from trademonitor.core.recovery import FreshnessRelation, compare_observation_time, runtime_fingerprint
from trademonitor.domain.enums import AgentVerdict, AttentionLevel, AttentionStatus, EntryIntentState, HealthStatus, RiskDecision, ExitAction, ExitProposalClass
from trademonitor.domain.events import DomainEvent
from trademonitor.domain.models import (
    AttentionItem,
    EntryIntentRecord,
    EntryMarketSnapshot,
    EntryReviewRecord,
    EntryRiskProposal,
    RiskDecisionRecord,
    RiskProfile,
    RiskProfileChange,
    EpisodeRecord,
    IntakeResult,
    NormalizedTradeIntent,
    PositionRecord,
    PositionAdoptionRequest,
    PositionManagementProfile,
    ManagementRuleSpec,
    PositionManagementRule,
    PositionManagementSnapshot,
    ManagementRuleEvaluation,
    ExitProposal,
    PositionConversionRequest,
)
from trademonitor.entry.monitor import EntryMonitor
from trademonitor.entry.review import EntryReviewCoordinator
from trademonitor.persistence.repository import RuntimeRepository
from trademonitor.positions.manager import PositionAdoptionError, PositionManager
from trademonitor.positions.rules import ManagementRuleEngine
from trademonitor.positions.exit import ExitMonitor
from trademonitor.risk.engine import RiskEngine


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
        self._management_rules = ManagementRuleEngine(repository, self._positions)
        self._exit = ExitMonitor(repository, self._positions)
        self._intake = TradeIntakeManager(
            repository, positions_provider=lambda: self._positions.list_positions(open_only=True)
        )
        self._entry = EntryMonitor(repository)
        self._entry_review = EntryReviewCoordinator(repository)
        self._risk = RiskEngine(repository)
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
            broker_ctx = self._contexts.get("broker")
            broker_ctx.data.setdefault("status", "NOT_RECONCILED")
            # Persisted broker truth is useful last-known context, but Risk Management
            # must require a fresh reconciliation in the current runtime before
            # authorising new exposure.
            broker_ctx.patch({"runtime_reconciled": False})
            self._contexts.get("decision").data.setdefault("attention_queue", [])
            profile = self._risk.ensure_profile()
            self._contexts.get("risk").patch({
                "status": "READY",
                "active_profile_version": profile.version,
                "profile": profile.to_record(),
                "authority": "HIGHEST_RUNTIME",
            })
            self._refresh_position_context()
            self._refresh_entry_context()
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


    def ingest_trade_observation(
        self,
        *,
        src_id: str,
        source: str,
        observed_at: datetime,
        intent: NormalizedTradeIntent,
        raw_payload: dict[str, Any] | None = None,
    ) -> IntakeResult:
        """Coordinate one intake observation through the specialist Intake domain."""
        with self._lock:
            self._ensure_started()
            result, events = self._intake.ingest(
                src_id=src_id,
                source=source,
                observed_at=observed_at,
                intent=intent,
                raw_payload=raw_payload,
            )
            for event in events:
                self._record_event(event)
            counts = self._intake.snapshot()
            trade = self._contexts.get("trade")
            trade.patch({"intake": counts})
            self._repository.save_context(trade.to_record())
            return result

    def intake_snapshot(self) -> dict[str, int]:
        """Return durable intake counts without exposing persistence internals."""
        with self._lock:
            self._ensure_started()
            return self._intake.snapshot()


    def create_entry_intent(self, *, episode: EpisodeRecord, **kwargs) -> EntryIntentRecord:
        """Admit one Episode into deterministic entry monitoring (PAPER only)."""
        with self._lock:
            self._ensure_started()
            intent, events = self._entry.create_for_episode(episode=episode, **kwargs)
            for event in events:
                self._record_event(event)
            self._refresh_entry_context()
            return intent

    def evaluate_entry_intent(self, entry_intent_id: str, snapshot: EntryMarketSnapshot) -> EntryIntentRecord:
        """Evaluate trigger/confirmation/current-market validity without execution."""
        with self._lock:
            self._ensure_started()
            intent, events = self._entry.evaluate(entry_intent_id, snapshot)
            for event in events:
                self._record_event(event)
            self._refresh_entry_context()
            return intent

    def rearm_entry_intent(self, entry_intent_id: str, *, at: datetime, reason: str) -> EntryIntentRecord:
        with self._lock:
            self._ensure_started()
            intent, events = self._entry.rearm(entry_intent_id, at=at, reason=reason)
            for event in events:
                self._record_event(event)
            self._refresh_entry_context()
            return intent

    def entry_snapshot(self) -> list[EntryIntentRecord]:
        with self._lock:
            self._ensure_started()
            return self._entry.list_active()

    def request_entry_agent_review(
        self,
        entry_intent_id: str,
        gateway: AgentGateway,
        *,
        requested_at: datetime | None = None,
    ) -> EntryIntentRecord:
        """Ask the separate Agents service to independently validate a ready entry.

        APPROVE advances only to READY_FOR_RISK. REJECT/RETREAT_WAIT or service
        failure creates a User decision point. No execution/Risk action occurs here.
        """
        with self._lock:
            self._ensure_started()
            intent, review, events = self._entry_review.request_review(
                entry_intent_id, gateway, requested_at=requested_at
            )
            for event in events:
                self._record_event(event)
            if intent.state == EntryIntentState.USER_DECISION_PENDING:
                verdict = (
                    review.result.verdict.value
                    if review.result is not None
                    else "AGENT_UNAVAILABLE"
                )
                suggestion = (
                    f" Suggestion: {review.result.suggestion}"
                    if review.result is not None and review.result.suggestion
                    else ""
                )
                self.add_attention(
                    level=AttentionLevel.ATTENTION,
                    source="ENTRY",
                    title=f"User decision required: {entry_intent_id}",
                    detail=(
                        f"Agents outcome={verdict}. Choose APPROVE / REJECT / "
                        f"RETREAT_WAIT for this entry.{suggestion}"
                    ),
                )
            self._refresh_entry_context()
            return intent

    def resolve_entry_agent_decision(
        self,
        entry_intent_id: str,
        decision: AgentVerdict | str,
        *,
        at: datetime,
        reason: str,
    ) -> EntryIntentRecord:
        """Record the User's higher-authority decision after Agent disagreement."""
        with self._lock:
            self._ensure_started()
            intent, _review, events = self._entry_review.resolve_user_decision(
                entry_intent_id, decision, at=at, reason=reason
            )
            for event in events:
                self._record_event(event)
            self._resolve_matching_attention(
                source="ENTRY", title=f"User decision required: {entry_intent_id}"
            )
            self._refresh_entry_context()
            return intent

    def entry_review_snapshot(
        self, *, entry_intent_id: str | None = None
    ) -> list[EntryReviewRecord]:
        with self._lock:
            self._ensure_started()
            return self._entry_review.list_reviews(entry_intent_id=entry_intent_id)

    def evaluate_entry_risk(
        self,
        entry_intent_id: str,
        proposal: EntryRiskProposal,
        *,
        evaluated_at: datetime | None = None,
    ) -> RiskDecisionRecord:
        """Run the highest-authority pre-trade Risk Management gate.

        This target still creates no ExecutionRequest. A PASS only establishes
        current RM permission for the evaluated proposal.
        """
        with self._lock:
            self._ensure_started()
            intent = self._repository.get_entry_intent(entry_intent_id)
            if intent is None:
                raise KeyError(f"Unknown entry intent: {entry_intent_id}")
            updated, decision, events = self._risk.evaluate_entry(
                intent=intent,
                proposal=proposal,
                positions=self._positions.list_positions(open_only=True),
                broker_context=dict(self._contexts.get("broker").data),
                evaluated_at=evaluated_at,
            )
            for event in events:
                self._record_event(event)
            risk = self._contexts.get("risk")
            risk.patch({
                "status": "BLOCKED" if decision.decision == RiskDecision.BLOCK else "PASS",
                "active_profile_version": decision.profile_version,
                "last_decision_id": decision.decision_id,
                "last_entry_intent_id": entry_intent_id,
                "last_decision": decision.decision.value,
                "last_reasons": list(decision.reasons),
                "metrics": dict(decision.metrics),
            })
            self._repository.save_context(risk.to_record())
            if decision.decision == RiskDecision.BLOCK:
                self.add_attention(
                    level=AttentionLevel.ATTENTION,
                    source="RISK",
                    title=f"Risk blocked entry: {entry_intent_id}",
                    detail=(
                        "Risk Management blocked the proposed new exposure. "
                        + ", ".join(decision.reasons)
                        + ". Normal trade commands cannot override this block."
                    ),
                )
            else:
                self._resolve_matching_attention(
                    source="RISK", title=f"Risk blocked entry: {entry_intent_id}"
                )
            self._refresh_entry_context()
            return decision

    def rearm_risk_blocked_entry(
        self, entry_intent_id: str, *, at: datetime, reason: str
    ) -> EntryIntentRecord:
        """Explicitly return a blocked entry to READY_FOR_RISK for a fresh gate.

        Risk-profile changes never revive blocked trades automatically. This method
        is the deliberate re-evaluation boundary.
        """
        with self._lock:
            self._ensure_started()
            intent, event = self._risk.rearm_blocked_entry(
                entry_intent_id, at=at, reason=reason
            )
            self._record_event(event)
            self._resolve_matching_attention(
                source="RISK", title=f"Risk blocked entry: {entry_intent_id}"
            )
            self._refresh_entry_context()
            return intent

    def risk_decision_snapshot(
        self, *, entry_intent_id: str | None = None
    ) -> list[RiskDecisionRecord]:
        with self._lock:
            self._ensure_started()
            return self._risk.list_decisions(entry_intent_id=entry_intent_id)

    def active_risk_profile(self) -> RiskProfile:
        with self._lock:
            self._ensure_started()
            return self._risk.active_profile()

    def admin_propose_risk_profile_change(self, **kwargs) -> RiskProfileChange:
        """Setup/Admin path: propose only; active RM is unchanged."""
        with self._lock:
            self._ensure_started()
            change, event = self._risk.admin_propose_profile_change(**kwargs)
            self._record_event(event)
            return change

    def admin_confirm_risk_profile_change(
        self,
        change_id: str,
        *,
        confirmation: str,
        confirmed_at: datetime | None = None,
    ) -> RiskProfile:
        """Setup/Admin path: deliberate confirmation activates a new version."""
        with self._lock:
            self._ensure_started()
            profile, change, events = self._risk.admin_confirm_profile_change(
                change_id, confirmation=confirmation, confirmed_at=confirmed_at
            )
            for event in events:
                self._record_event(event)
            risk = self._contexts.get("risk")
            risk.patch({
                "status": "READY",
                "active_profile_version": profile.version,
                "profile": profile.to_record(),
                "last_profile_change_id": change.change_id,
            })
            self._repository.save_context(risk.to_record())
            return profile

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
        """Record/publish an event once; exact replays are harmless."""
        with self._lock:
            self._ensure_started()
            self._record_event(event)

    def mark_context_stale(
        self,
        context_name: str,
        *,
        domain: str,
        reason: str,
        impact: Sequence[str] = (),
    ) -> None:
        """Mark one domain/context stale without collapsing unrelated peers."""
        with self._lock:
            self._ensure_started()
            self.patch_context(
                context_name,
                {"status": "STALE"},
                source=domain.upper(),
                reason=reason,
            )
            self.report_domain_health(
                DomainHealthReport.create(
                    domain,
                    HealthStatus.DEGRADED,
                    reason,
                    impact=impact or (f"{context_name} context is stale",),
                )
            )
            self._record_event(
                DomainEvent.create(
                    "CONTEXT_MARKED_STALE",
                    source=domain.upper(),
                    payload={"context": context_name, "reason": reason, "impact": list(impact)},
                )
            )

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
            normalized_source = source.upper()
            for existing in self.attention_snapshot(active_only=True):
                if existing.source == normalized_source and existing.title == title:
                    return existing
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

                previous_observed_at = self._last_broker_observed_at(snapshot.broker)
                freshness = compare_observation_time(snapshot.observed_at, previous_observed_at)
                if freshness in {FreshnessRelation.REPLAY, FreshnessRelation.STALE}:
                    # An exact replay is still a successful current-runtime broker
                    # confirmation. It changes no business state, but it satisfies
                    # the Risk gate's requirement that broker truth was checked in
                    # this runtime. A stale older snapshot does not.
                    if freshness == FreshnessRelation.REPLAY:
                        broker_ctx = self._contexts.get("broker")
                        broker_ctx.patch({"runtime_reconciled": True})
                        self._repository.save_context(broker_ctx.to_record())
                    self._record_event(
                        DomainEvent.create(
                            "BROKER_SNAPSHOT_IGNORED",
                            source="BROKER",
                            payload={
                                "broker": snapshot.broker,
                                "relation": freshness.value,
                                "incoming_observed_at": snapshot.observed_at.isoformat(),
                                "last_accepted_observed_at": (
                                    previous_observed_at.isoformat() if previous_observed_at else None
                                ),
                            },
                            occurred_at=snapshot.observed_at,
                        )
                    )
                    return self._positions.list_positions(broker=snapshot.broker)

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
                    "runtime_reconciled": True,
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
                for position in positions:
                    if not position.is_open:
                        for event in self._exit.reconcile_with_broker(position.position_id, at=snapshot.observed_at):
                            self._record_event(event)
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
                self._resolve_matching_attention(
                    source="BROKER", title="Broker reconciliation unavailable"
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
                    {"status": "UNAVAILABLE", "read_only": True, "runtime_reconciled": False},
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

    def adopt_position(
        self, request: PositionAdoptionRequest
    ) -> tuple[PositionRecord, PositionManagementProfile]:
        """Explicitly cross one broker position from UNMANAGED to MANAGED.

        Adoption is a TM authority change only; it never writes to the broker.
        Current-runtime broker reconciliation is required so adoption is based on
        current broker truth rather than a persisted last-known position.
        """
        with self._lock:
            self._ensure_started()
            broker_ctx = self._contexts.get("broker").data
            if not broker_ctx.get("runtime_reconciled", False):
                raise PositionAdoptionError(
                    "Current-runtime broker reconciliation is required before adoption"
                )
            position = self._positions.get_position(request.position_id)
            if position is None:
                raise PositionAdoptionError(f"Unknown position: {request.position_id}")
            reconciled_broker = broker_ctx.get("broker")
            if reconciled_broker and position.broker != reconciled_broker:
                raise PositionAdoptionError(
                    f"Position broker {position.broker!r} is not the currently reconciled broker {reconciled_broker!r}"
                )
            adopted, profile, events = self._positions.adopt(request)
            for event in events:
                self._record_event(event)
            self._refresh_position_context(source="POSITION")
            return adopted, profile


    def add_position_management_rule(
        self,
        position_id: str,
        spec: ManagementRuleSpec,
        *,
        created_at: datetime,
    ) -> PositionManagementRule:
        """Attach one explicit deterministic rule to an open MANAGED position."""
        with self._lock:
            self._ensure_started()
            rule, events = self._management_rules.add_rule(
                position_id, spec, created_at=created_at
            )
            for event in events:
                self._record_event(event)
            self._refresh_position_context(source="POSITION")
            return rule

    def install_position_management_policy(
        self,
        position_id: str,
        policy_name: str,
        specs: list[ManagementRuleSpec],
        *,
        created_at: datetime,
    ) -> list[PositionManagementRule]:
        """Install a named batch of deterministic management rules."""
        with self._lock:
            self._ensure_started()
            rules, events = self._management_rules.install_policy(
                position_id, policy_name, specs, created_at=created_at
            )
            for event in events:
                self._record_event(event)
            self._refresh_position_context(source="POSITION")
            return rules

    def evaluate_position_management(
        self,
        position_id: str,
        snapshot: PositionManagementSnapshot,
    ) -> list[ManagementRuleEvaluation]:
        """Evaluate managed-position rules; emits signals only, never execution."""
        with self._lock:
            self._ensure_started()
            evaluations, events = self._management_rules.evaluate(position_id, snapshot)
            for event in events:
                self._record_event(event)
            _proposals, exit_events = self._exit.consume_rule_evaluations(
                position_id, evaluations, at=snapshot.observed_at
            )
            for event in exit_events:
                self._record_event(event)
            self._refresh_position_context(source="POSITION")
            return evaluations

    def cancel_position_management_rule(
        self,
        rule_id: str,
        *,
        at: datetime,
        cancelled_by: str,
        reason: str,
    ) -> PositionManagementRule:
        with self._lock:
            self._ensure_started()
            rule, events = self._management_rules.cancel_rule(
                rule_id, at=at, cancelled_by=cancelled_by, reason=reason
            )
            for event in events:
                self._record_event(event)
            self._refresh_position_context(source="POSITION")
            return rule

    def position_management_rules_snapshot(
        self, *, position_id: str | None = None, active_only: bool = False
    ) -> list[PositionManagementRule]:
        with self._lock:
            self._ensure_started()
            return self._management_rules.list_rules(
                position_id=position_id, active_only=active_only
            )

    def propose_position_exit(
        self,
        position_id: str,
        *,
        proposal_class: ExitProposalClass,
        action: ExitAction,
        at: datetime,
        created_by: str,
        reason: str,
        requested_quantity: int | None = None,
        requested_percent: str | int | float | None = None,
    ) -> ExitProposal:
        """Create a strategic/deterministic PAPER exit proposal; never broker execution."""
        with self._lock:
            self._ensure_started()
            proposal, events = self._exit.propose_exit(
                position_id,
                proposal_class=proposal_class,
                action=action,
                at=at,
                created_by=created_by,
                reason=reason,
                requested_quantity=requested_quantity,
                requested_percent=requested_percent,
            )
            for event in events:
                self._record_event(event)
            self._refresh_position_context(source="EXIT")
            return proposal

    def evaluate_day_end(self, position_id: str, *, at: datetime, cutoff_at: datetime) -> ExitProposal | None:
        with self._lock:
            self._ensure_started()
            proposal, events = self._exit.day_end_review(position_id, at=at, cutoff_at=cutoff_at)
            for event in events:
                self._record_event(event)
            self._refresh_position_context(source="EXIT")
            return proposal

    def convert_managed_position(self, request: PositionConversionRequest) -> PositionManagementProfile:
        with self._lock:
            self._ensure_started()
            profile, events = self._exit.convert_position(request)
            for event in events:
                self._record_event(event)
            self._refresh_position_context(source="POSITION")
            return profile

    def exit_proposals_snapshot(self, *, position_id: str | None = None, active_only: bool = False) -> list[ExitProposal]:
        with self._lock:
            self._ensure_started()
            return self._exit.list_proposals(position_id=position_id, active_only=active_only)

    def position_management_profile(
        self, position_id: str
    ) -> PositionManagementProfile | None:
        with self._lock:
            self._ensure_started()
            return self._positions.management_profile(position_id)

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

    def runtime_fingerprint(self) -> str:
        """Stable business-state fingerprint used by PAPER replay validation."""
        with self._lock:
            self._ensure_started()
            return runtime_fingerprint(self.status_snapshot(), self.positions_snapshot())

    def _last_broker_observed_at(self, broker_name: str) -> datetime | None:
        broker_ctx = self._contexts.get("broker").data
        if broker_ctx.get("broker") != broker_name:
            return None
        value = broker_ctx.get("observed_at")
        if not value:
            return None
        return datetime.fromisoformat(str(value))

    def _resolve_matching_attention(self, *, source: str, title: str) -> None:
        matches = [
            item
            for item in self.attention_snapshot(active_only=True)
            if item.source == source.upper() and item.title == title
        ]
        for item in matches:
            self.resolve_attention(item.attention_id, source=source.upper())

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
        inserted = self._repository.append_event(event.to_record())
        if inserted:
            self._event_bus.publish(event)

    def _persist_all_contexts(self) -> None:
        for context in self._contexts.contexts.values():
            self._repository.save_context(context.to_record())

    def _refresh_entry_context(self) -> None:
        active = self._entry.list_active()
        counts: dict[str, int] = {}
        for item in active:
            counts[item.state.value] = counts.get(item.state.value, 0) + 1
        reviews = self._entry_review.list_reviews()
        review_counts: dict[str, int] = {}
        for review in reviews:
            review_counts[review.status.value] = review_counts.get(review.status.value, 0) + 1
        trade = self._contexts.get("trade")
        trade.patch(
            {
                "entry_monitoring": {"active": len(active), "by_state": counts},
                "entry_agent_reviews": {"total": len(reviews), "by_status": review_counts},
            }
        )
        self._repository.save_context(trade.to_record())

    def _refresh_position_context(self, *, source: str | None = None) -> None:
        positions = self._repository.list_positions()
        open_positions = [position for position in positions if position.is_open]
        rules = self._management_rules.list_rules()
        active_rules = [r for r in rules if r.status.value not in {"TRIGGERED", "CANCELLED"}]
        triggered_rules = [r for r in rules if r.status.value == "TRIGGERED"]
        data = {
            "total_known": len(positions),
            "open": len(open_positions),
            "closed": len(positions) - len(open_positions),
            "managed_open": len([p for p in open_positions if p.is_managed]),
            "unmanaged_open": len([p for p in open_positions if not p.is_managed]),
            "management_rules": {
                "total": len(rules),
                "active": len(active_rules),
                "triggered": len(triggered_rules),
            },
            "exit_proposals": {
                "total": len(self._exit.list_proposals()),
                "pending": len(self._exit.list_proposals(active_only=True)),
            },
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
