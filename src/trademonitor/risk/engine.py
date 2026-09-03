"""TM2/TGT4 Risk Management entry gate.

Risk Management is the highest runtime operational authority inside TradeMonitor.
This module evaluates proposed new exposure against the active, versioned risk
profile and current broker-confirmed account state. It never sends broker orders.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping, Sequence
from uuid import uuid4

from trademonitor.domain.enums import EntryIntentState, ManagementStatus, RiskChangeStatus, RiskDecision
from trademonitor.domain.events import DomainEvent
from trademonitor.domain.models import (
    EntryIntentRecord,
    EntryRiskProposal,
    PositionRecord,
    RiskDecisionRecord,
    RiskProfile,
    RiskProfileChange,
    utc_now,
)
from trademonitor.persistence.repository import RuntimeRepository


class RiskEngine:
    """Authoritative entry-risk gate plus deliberate Setup/Admin profile changes."""

    BOOTSTRAP_REASON = "TM2/TGT4 bootstrap risk profile; numeric limits not yet configured"

    def __init__(self, repository: RuntimeRepository) -> None:
        self._repository = repository

    def ensure_profile(self) -> RiskProfile:
        profile = self._repository.get_active_risk_profile()
        if profile is None:
            profile = RiskProfile(version=1, reason=self.BOOTSTRAP_REASON)
            self._repository.save_risk_profile(profile.to_record())
        return profile

    def active_profile(self) -> RiskProfile:
        return self.ensure_profile()

    def evaluate_entry(
        self,
        *,
        intent: EntryIntentRecord,
        proposal: EntryRiskProposal,
        positions: Sequence[PositionRecord],
        broker_context: Mapping[str, Any],
        evaluated_at: datetime | None = None,
    ) -> tuple[EntryIntentRecord, RiskDecisionRecord, list[DomainEvent]]:
        """Evaluate one READY_FOR_RISK entry against current account truth.

        A PASS is permission to proceed to a later execution-authorisation stage;
        it is not an ExecutionRequest and this module has no broker-write path.
        """
        if intent.state != EntryIntentState.READY_FOR_RISK:
            raise ValueError("Risk gate requires READY_FOR_RISK entry intent")
        if proposal.entry_intent_id != intent.entry_intent_id:
            raise ValueError("Risk proposal does not belong to the supplied entry intent")

        profile = self.ensure_profile()
        at = evaluated_at or utc_now()
        reasons: list[str] = []
        metrics = self._risk_metrics(positions, proposal)

        # Broker truth is required before authorising creation of new exposure.
        if (
            broker_context.get("status") != "RECONCILED"
            or not broker_context.get("observed_at")
            or broker_context.get("runtime_reconciled") is not True
        ):
            reasons.append("BROKER_TRUTH_NOT_CURRENT")

        if profile.max_position_value is not None and proposal.planned_position_value > profile.max_position_value:
            reasons.append("MAX_POSITION_VALUE_EXCEEDED")

        if profile.max_trade_loss is not None:
            if proposal.planned_max_loss is None:
                reasons.append("PLANNED_MAX_LOSS_UNKNOWN")
            elif proposal.planned_max_loss > profile.max_trade_loss:
                reasons.append("MAX_TRADE_LOSS_EXCEEDED")

        if profile.max_open_positions is not None and metrics["open_position_count"] >= profile.max_open_positions:
            reasons.append("MAX_OPEN_POSITIONS_REACHED")

        if profile.max_total_exposure is not None:
            projected = Decimal(metrics["projected_total_exposure"])
            if projected > profile.max_total_exposure:
                reasons.append("MAX_TOTAL_EXPOSURE_EXCEEDED")

        decision = RiskDecision.BLOCK if reasons else RiskDecision.PASS
        record = RiskDecisionRecord(
            decision_id=f"RD-{uuid4()}",
            entry_intent_id=intent.entry_intent_id,
            profile_version=profile.version,
            decision=decision,
            evaluated_at=at,
            reasons=tuple(reasons),
            metrics={
                **metrics,
                "profile": profile.to_record(),
                "broker": broker_context.get("broker"),
                "broker_observed_at": broker_context.get("observed_at"),
            },
            proposal=proposal,
        )
        self._repository.save_risk_decision(record.to_record())

        state = EntryIntentState.RISK_BLOCKED if decision == RiskDecision.BLOCK else EntryIntentState.RISK_APPROVED
        reason = (
            "Risk Management BLOCK: " + ", ".join(reasons)
            if reasons
            else f"Risk Management PASS under profile v{profile.version}"
        )
        updated = replace(intent, state=state, updated_at=at, last_reason=reason)
        self._repository.save_entry_intent(updated.to_record())

        event_name = "ENTRY_RISK_BLOCKED" if decision == RiskDecision.BLOCK else "ENTRY_RISK_PASSED"
        events = [
            DomainEvent.create(
                event_name,
                source="RISK",
                occurred_at=at,
                payload={
                    "decision_id": record.decision_id,
                    "entry_intent_id": intent.entry_intent_id,
                    "decision": decision.value,
                    "risk_profile_version": profile.version,
                    "reasons": list(record.reasons),
                    "metrics": dict(record.metrics),
                    "proposal": proposal.to_record(),
                },
            )
        ]
        return updated, record, events

    def rearm_blocked_entry(
        self, entry_intent_id: str, *, at: datetime, reason: str
    ) -> tuple[EntryIntentRecord, DomainEvent]:
        if not reason.strip():
            raise ValueError("Risk re-evaluation requires a reason")
        intent = self._repository.get_entry_intent(entry_intent_id)
        if intent is None:
            raise KeyError(f"Unknown entry intent: {entry_intent_id}")
        if intent.state != EntryIntentState.RISK_BLOCKED:
            raise ValueError("Only RISK_BLOCKED entries can be explicitly rearmed for Risk")
        updated = replace(
            intent,
            state=EntryIntentState.READY_FOR_RISK,
            updated_at=at,
            last_reason=f"Explicit Risk re-evaluation requested: {reason.strip()}",
        )
        self._repository.save_entry_intent(updated.to_record())
        event = DomainEvent.create(
            "ENTRY_RISK_REEVALUATION_REQUESTED",
            source="RISK",
            occurred_at=at,
            payload={
                "entry_intent_id": entry_intent_id,
                "reason": reason.strip(),
            },
        )
        return updated, event

    def list_decisions(self, *, entry_intent_id: str | None = None) -> list[RiskDecisionRecord]:
        return self._repository.list_risk_decisions(entry_intent_id=entry_intent_id)

    # ------------------------------------------------------------------
    # Setup/Admin-only risk configuration path
    # ------------------------------------------------------------------
    def admin_propose_profile_change(
        self,
        *,
        reason: str,
        requested_at: datetime | None = None,
        max_position_value=None,
        max_trade_loss=None,
        max_open_positions: int | None = None,
        max_total_exposure=None,
    ) -> tuple[RiskProfileChange, DomainEvent]:
        """Create a pending risk-profile change; does not alter active risk."""
        if not reason.strip():
            raise ValueError("Admin risk change requires an explicit reason")
        # Validate proposed values by constructing a throwaway profile.
        RiskProfile(
            version=1,
            reason=reason,
            max_position_value=max_position_value,
            max_trade_loss=max_trade_loss,
            max_open_positions=max_open_positions,
            max_total_exposure=max_total_exposure,
        )
        at = requested_at or utc_now()
        proposed = {
            "max_position_value": None if max_position_value is None else str(max_position_value),
            "max_trade_loss": None if max_trade_loss is None else str(max_trade_loss),
            "max_open_positions": max_open_positions,
            "max_total_exposure": None if max_total_exposure is None else str(max_total_exposure),
        }
        change = RiskProfileChange(
            change_id=f"RC-{uuid4()}",
            status=RiskChangeStatus.PENDING,
            proposed=proposed,
            reason=reason.strip(),
            requested_at=at,
        )
        self._repository.save_risk_profile_change(change.to_record())
        return change, DomainEvent.create(
            "RISK_PROFILE_CHANGE_PROPOSED",
            source="RISK_ADMIN",
            occurred_at=at,
            payload=change.to_record(),
        )

    def admin_confirm_profile_change(
        self,
        change_id: str,
        *,
        confirmation: str,
        confirmed_at: datetime | None = None,
    ) -> tuple[RiskProfile, RiskProfileChange, list[DomainEvent]]:
        """Activate a pending change only after deliberate literal confirmation."""
        if confirmation != "CONFIRM":
            raise ValueError('Risk profile change requires confirmation="CONFIRM"')
        change = self._repository.get_risk_profile_change(change_id)
        if change is None:
            raise KeyError(f"Unknown risk profile change: {change_id}")
        if change.status != RiskChangeStatus.PENDING:
            raise ValueError("Risk profile change is not pending")
        current = self.ensure_profile()
        at = confirmed_at or utc_now()
        profile = RiskProfile(
            version=current.version + 1,
            created_at=at,
            reason=change.reason,
            max_position_value=change.proposed.get("max_position_value"),
            max_trade_loss=change.proposed.get("max_trade_loss"),
            max_open_positions=change.proposed.get("max_open_positions"),
            max_total_exposure=change.proposed.get("max_total_exposure"),
        )
        self._repository.save_risk_profile(profile.to_record())
        confirmed = replace(
            change,
            status=RiskChangeStatus.CONFIRMED,
            confirmed_at=at,
            resulting_profile_version=profile.version,
        )
        self._repository.save_risk_profile_change(confirmed.to_record())
        events = [
            DomainEvent.create(
                "RISK_PROFILE_CHANGE_CONFIRMED",
                source="RISK_ADMIN",
                occurred_at=at,
                payload={
                    "change_id": change.change_id,
                    "old_profile_version": current.version,
                    "new_profile": profile.to_record(),
                    "reason": change.reason,
                },
            )
        ]
        return profile, confirmed, events

    @staticmethod
    def _risk_metrics(positions: Sequence[PositionRecord], proposal: EntryRiskProposal) -> dict[str, Any]:
        open_positions = [p for p in positions if p.is_open]
        managed = [p for p in open_positions if p.management_status == ManagementStatus.MANAGED]
        unmanaged = [p for p in open_positions if p.management_status == ManagementStatus.UNMANAGED]
        current_exposure = sum(
            (abs(Decimal(p.quantity)) * (p.last_price if p.last_price is not None else p.average_price)
             for p in open_positions),
            Decimal("0"),
        )
        projected = current_exposure + proposal.planned_position_value
        return {
            "open_position_count": len(open_positions),
            "managed_open_count": len(managed),
            "unmanaged_open_count": len(unmanaged),
            "current_total_exposure": str(current_exposure),
            "planned_position_value": str(proposal.planned_position_value),
            "projected_total_exposure": str(projected),
            "planned_max_loss": None if proposal.planned_max_loss is None else str(proposal.planned_max_loss),
        }
