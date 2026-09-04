"""TM3/TGT3 Exit Monitor and position-evolution coordinator.

This module turns deterministic management signals or explicit strategic requests
into durable ExitProposal objects. It never writes to a broker and never creates
an ExecutionRequest; Module M remains outside this milestone.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from trademonitor.domain.enums import (
    ExitAction,
    ExitProposalClass,
    ExitProposalStatus,
    ManagementRuleType,
    ManagementSignal,
    ManagementStatus,
    PositionState,
    TradeType,
)
from trademonitor.domain.events import DomainEvent
from trademonitor.domain.models import (
    ExitProposal,
    ManagementRuleEvaluation,
    PositionConversionRequest,
    PositionManagementProfile,
)
from trademonitor.persistence.repository import RuntimeRepository
from trademonitor.positions.manager import PositionManager, UnmanagedPositionError


class ExitMonitorError(ValueError):
    pass


_PROTECTIVE_RULES = {
    ManagementRuleType.HARD_SL,
    ManagementRuleType.UNDERLYING_INVALIDATION,
}


class ExitMonitor:
    """Own exit proposals, duplicate suppression, and holding-intent evolution."""

    def __init__(self, repository: RuntimeRepository, positions: PositionManager) -> None:
        self._repository = repository
        self._positions = positions

    def consume_rule_evaluations(
        self,
        position_id: str,
        evaluations: list[ManagementRuleEvaluation],
        *,
        at: datetime,
    ) -> tuple[list[ExitProposal], list[DomainEvent]]:
        """Convert triggered EXIT_REVIEW signals into durable exit proposals."""
        triggered = [
            e for e in evaluations if e.triggered and e.signal == ManagementSignal.EXIT_REVIEW
        ]
        if not triggered:
            return [], []

        proposals: list[ExitProposal] = []
        events: list[DomainEvent] = []
        for evaluation in triggered:
            proposal_class = (
                ExitProposalClass.PROTECTIVE
                if evaluation.rule_type in _PROTECTIVE_RULES
                else (
                    ExitProposalClass.STRATEGIC
                    if evaluation.rule_type == ManagementRuleType.HORIZON
                    else ExitProposalClass.DETERMINISTIC
                )
            )
            proposal, evs = self.propose_exit(
                position_id,
                proposal_class=proposal_class,
                action=ExitAction.EXIT_ALL,
                at=at,
                created_by="POSITION_RULE",
                reason=evaluation.reason,
                trigger_rule_id=evaluation.rule_id,
            )
            proposals.append(proposal)
            events.extend(evs)
        # return unique proposals in case several triggers coalesced into one
        unique = {p.proposal_id: p for p in proposals}
        return list(unique.values()), events

    def propose_exit(
        self,
        position_id: str,
        *,
        proposal_class: ExitProposalClass,
        action: ExitAction,
        at: datetime,
        created_by: str,
        reason: str,
        requested_quantity: int | None = None,
        requested_percent: Decimal | str | int | float | None = None,
        trigger_rule_id: str | None = None,
    ) -> tuple[ExitProposal, list[DomainEvent]]:
        position = self._require_open_managed(position_id)
        if not created_by.strip() or not reason.strip():
            raise ExitMonitorError("created_by and reason are required")
        pct = None if requested_percent is None else Decimal(str(requested_percent))
        self._validate_action(position.quantity, action, requested_quantity, pct)

        active = self._repository.list_exit_proposals(position_id=position_id, active_only=True)
        # Full-exit proposals claim the whole position. Any later full-exit trigger is
        # attached as another reason rather than creating a second future order path.
        existing_full = next((p for p in active if p.action == ExitAction.EXIT_ALL), None)
        if existing_full is not None and action != ExitAction.EXIT_ALL:
            # A pending full exit already claims all remaining exposure. A later
            # partial proposal must not create a competing future execution path.
            event = DomainEvent.create(
                "EXIT_TRIGGER_SUPPRESSED",
                source="EXIT",
                occurred_at=at,
                payload={
                    "position_id": position_id,
                    "existing_proposal_id": existing_full.proposal_id,
                    "suppressed_action": ExitAction(action).value,
                    "reason": "pending full exit already owns the position",
                },
            )
            return existing_full, [event]
        if action == ExitAction.EXIT_ALL and existing_full is not None:
            reasons = existing_full.reasons
            if reason not in reasons:
                reasons = (*reasons, reason)
            rule_ids = existing_full.trigger_rule_ids
            if trigger_rule_id and trigger_rule_id not in rule_ids:
                rule_ids = (*rule_ids, trigger_rule_id)
            updated = replace(existing_full, reasons=reasons, trigger_rule_ids=rule_ids, updated_at=at)
            self._repository.save_exit_proposal(updated.to_record())
            event = DomainEvent.create(
                "EXIT_TRIGGER_COALESCED",
                source="EXIT",
                occurred_at=at,
                payload={
                    "position_id": position_id,
                    "proposal_id": updated.proposal_id,
                    "reason": reason,
                    "trigger_rule_id": trigger_rule_id,
                },
            )
            return updated, [event]

        if action == ExitAction.EXIT_ALL:
            for pending in active:
                if pending.action == ExitAction.EXIT_ALL:
                    continue
                superseded = replace(
                    pending, status=ExitProposalStatus.SUPERSEDED, updated_at=at
                )
                self._repository.save_exit_proposal(superseded.to_record())

        proposal = ExitProposal(
            proposal_id=str(uuid4()),
            position_id=position_id,
            proposal_class=ExitProposalClass(proposal_class),
            action=ExitAction(action),
            requested_quantity=requested_quantity,
            requested_percent=pct,
            status=ExitProposalStatus.PENDING,
            reasons=(reason,),
            trigger_rule_ids=(() if trigger_rule_id is None else (trigger_rule_id,)),
            created_at=at,
            updated_at=at,
            created_by=created_by,
        )
        self._repository.save_exit_proposal(proposal.to_record())
        return proposal, [
            DomainEvent.create(
                "EXIT_PROPOSAL_CREATED",
                source="EXIT",
                occurred_at=at,
                payload={
                    "position_id": position_id,
                    "proposal_id": proposal.proposal_id,
                    "proposal_class": proposal.proposal_class.value,
                    "action": proposal.action.value,
                    "requested_quantity": proposal.requested_quantity,
                    "requested_percent": None if proposal.requested_percent is None else str(proposal.requested_percent),
                    "reason": reason,
                    "created_by": created_by,
                },
            )
        ]

    def day_end_review(
        self, position_id: str, *, at: datetime, cutoff_at: datetime
    ) -> tuple[ExitProposal | None, list[DomainEvent]]:
        """Protect DAY intent from accidental overnight carry."""
        self._require_open_managed(position_id)
        profile = self._require_profile(position_id)
        if profile.trade_type != TradeType.DAY or at < cutoff_at:
            return None, []
        return self.propose_exit(
            position_id,
            proposal_class=ExitProposalClass.DETERMINISTIC,
            action=ExitAction.EXIT_ALL,
            at=at,
            created_by="DAY_EOD_POLICY",
            reason=f"DAY end-of-day boundary reached at {cutoff_at.isoformat()}",
        )

    def convert_position(
        self, request: PositionConversionRequest
    ) -> tuple[PositionManagementProfile, list[DomainEvent]]:
        """Deliberately change holding intent; no broker operation is performed."""
        self._require_open_managed(request.position_id)
        current = self._require_profile(request.position_id)
        updated = PositionManagementProfile(
            position_id=current.position_id,
            asset_class=current.asset_class,
            instrument_type=current.instrument_type,
            trade_type=TradeType(request.new_trade_type),
            horizon_at=request.new_horizon_at,
            expiry_date=current.expiry_date,
            activated_at=request.requested_at,
            activated_by=request.requested_by,
            activation_reason=request.reason,
            notes=current.notes,
        )
        self._repository.save_position_management_profile(updated.to_record())
        return updated, [
            DomainEvent.create(
                "POSITION_TRADE_TYPE_CONVERTED",
                source="POSITION",
                occurred_at=request.requested_at,
                payload={
                    "position_id": request.position_id,
                    "old_trade_type": current.trade_type.value,
                    "new_trade_type": updated.trade_type.value,
                    "old_horizon_at": current.horizon_at.isoformat(),
                    "new_horizon_at": updated.horizon_at.isoformat(),
                    "requested_by": request.requested_by,
                    "reason": request.reason,
                },
            )
        ]

    def reconcile_with_broker(self, position_id: str, *, at: datetime) -> list[DomainEvent]:
        """Mark pending proposals satisfied when broker truth says exposure is gone."""
        position = self._positions.get_position(position_id)
        if position is None:
            return []
        if position.is_open:
            return []
        events: list[DomainEvent] = []
        for proposal in self._repository.list_exit_proposals(position_id=position_id, active_only=True):
            updated = replace(proposal, status=ExitProposalStatus.SATISFIED_BY_BROKER, updated_at=at)
            self._repository.save_exit_proposal(updated.to_record())
            events.append(DomainEvent.create(
                "EXIT_PROPOSAL_SATISFIED_BY_BROKER",
                source="EXIT",
                occurred_at=at,
                payload={"position_id": position_id, "proposal_id": proposal.proposal_id},
            ))
        return events

    def list_proposals(self, *, position_id: str | None = None, active_only: bool = False) -> list[ExitProposal]:
        return self._repository.list_exit_proposals(position_id=position_id, active_only=active_only)

    def _require_open_managed(self, position_id: str):
        position = self._positions.get_position(position_id)
        if position is None:
            raise ExitMonitorError(f"Unknown position: {position_id}")
        self._positions.require_managed(position)
        if position.state != PositionState.OPEN or position.quantity == 0:
            raise ExitMonitorError(f"Position {position_id} is not open")
        return position

    def _require_profile(self, position_id: str) -> PositionManagementProfile:
        profile = self._positions.management_profile(position_id)
        if profile is None:
            raise ExitMonitorError(f"Managed position {position_id} has no management profile")
        return profile

    @staticmethod
    def _validate_action(quantity: int, action: ExitAction, requested_quantity: int | None, pct: Decimal | None) -> None:
        size = abs(quantity)
        if action == ExitAction.EXIT_ALL:
            if requested_quantity is not None or pct is not None:
                raise ExitMonitorError("EXIT_ALL does not accept quantity/percent")
            return
        if action == ExitAction.EXIT_QTY:
            if requested_quantity is None or requested_quantity <= 0 or requested_quantity > size:
                raise ExitMonitorError("EXIT_QTY requires 0 < quantity <= open quantity")
            if pct is not None:
                raise ExitMonitorError("EXIT_QTY does not accept percent")
            return
        if action == ExitAction.EXIT_PERCENT:
            if pct is None or pct <= 0 or pct > 100:
                raise ExitMonitorError("EXIT_PERCENT requires 0 < percent <= 100")
            if requested_quantity is not None:
                raise ExitMonitorError("EXIT_PERCENT does not accept quantity")
            return
        raise ExitMonitorError(f"Unsupported exit action: {action}")
