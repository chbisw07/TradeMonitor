"""TM4/TGT1 execution-request handoff construction.

This module sits upstream of Module M. It turns already-authorized entry/exit
business decisions into immutable deployment requests. It never talks to a
broker.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from trademonitor.domain.enums import (
    EntryIntentState,
    ExecutionPurpose,
    ExecutionRequestStatus,
    ExitAction,
    ExitProposalStatus,
    ManagementStatus,
    OrderSide,
    OrderType,
    PositionState,
    RiskDecision,
)
from trademonitor.domain.models import ExecutionRequest, ExitProposal, PositionRecord, RiskDecisionRecord
from trademonitor.persistence.repository import RuntimeRepository


class ExecutionAuthorizationError(PermissionError):
    """Raised when an upstream authority has not actually authorized deployment."""


class ExecutionRequestBuilder:
    """Create durable broker-ready requests without performing deployment."""

    def __init__(self, repository: RuntimeRepository) -> None:
        self._repository = repository

    def from_entry(
        self,
        *,
        entry_intent_id: str,
        risk_decision_id: str,
        broker: str,
        exchange: str,
        product: str,
        side: OrderSide,
        order_type: OrderType,
        created_at: datetime,
    ) -> ExecutionRequest:
        intent = self._repository.get_entry_intent(entry_intent_id)
        if intent is None:
            raise KeyError(f"Unknown entry intent: {entry_intent_id}")
        if intent.state != EntryIntentState.RISK_APPROVED:
            raise ExecutionAuthorizationError("Entry execution requires RISK_APPROVED intent")

        decision = self._repository.get_risk_decision(risk_decision_id)
        if decision is None:
            raise KeyError(f"Unknown Risk decision: {risk_decision_id}")
        latest = self._repository.get_latest_risk_decision(entry_intent_id)
        if latest is None or latest.decision_id != decision.decision_id:
            raise ExecutionAuthorizationError("Risk decision is not the latest decision for this entry")
        if decision.entry_intent_id != entry_intent_id or decision.decision != RiskDecision.PASS:
            raise ExecutionAuthorizationError("Entry execution requires a matching Risk PASS")

        profile = self._repository.get_active_risk_profile()
        if profile is None or profile.version != decision.profile_version:
            raise ExecutionAuthorizationError("Risk permission is stale after Risk profile change")

        symbol = intent.contract_symbol or intent.underlying
        if not symbol:
            raise ValueError("Executable entry requires a resolved symbol/contract")

        idem = f"ENTRY:{entry_intent_id}:{decision.decision_id}"
        existing = self._repository.get_execution_request_by_idempotency_key(idem)
        if existing is not None:
            return existing

        price = decision.proposal.planned_entry_price if OrderType(order_type) == OrderType.LIMIT else None
        req = ExecutionRequest(
            request_id=f"ER-{uuid4()}",
            idempotency_key=idem,
            purpose=ExecutionPurpose.ENTRY,
            source_id=entry_intent_id,
            broker=broker,
            exchange=exchange,
            symbol=symbol,
            product=product,
            side=OrderSide(side),
            quantity=decision.proposal.planned_qty,
            order_type=OrderType(order_type),
            limit_price=price,
            status=ExecutionRequestStatus.READY,
            created_at=created_at,
            updated_at=created_at,
            risk_decision_id=decision.decision_id,
            risk_profile_version=decision.profile_version,
        )
        self._repository.save_execution_request(req.to_record())
        return req

    def from_exit(
        self,
        *,
        exit_proposal_id: str,
        broker: str,
        order_type: OrderType,
        created_at: datetime,
        limit_price: Decimal | str | int | float | None = None,
    ) -> ExecutionRequest:
        proposal = self._repository.get_exit_proposal(exit_proposal_id)
        if proposal is None:
            raise KeyError(f"Unknown exit proposal: {exit_proposal_id}")
        if proposal.status != ExitProposalStatus.APPROVED:
            raise ExecutionAuthorizationError("Exit execution requires APPROVED exit proposal")

        position = self._repository.get_position(proposal.position_id)
        if position is None:
            raise KeyError(f"Unknown position: {proposal.position_id}")
        if position.management_status != ManagementStatus.MANAGED:
            raise ExecutionAuthorizationError("UNMANAGED position cannot create an exit ExecutionRequest")
        if position.state != PositionState.OPEN or position.quantity == 0:
            raise ExecutionAuthorizationError("Exit execution requires current open broker exposure")
        if position.broker != broker:
            raise ExecutionAuthorizationError("Exit request broker must match position broker truth")

        quantity = self._exit_quantity(position, proposal)
        side = OrderSide.SELL if position.quantity > 0 else OrderSide.BUY
        idem = f"EXIT:{exit_proposal_id}"
        existing = self._repository.get_execution_request_by_idempotency_key(idem)
        if existing is not None:
            return existing

        price = None if OrderType(order_type) == OrderType.MARKET else Decimal(str(limit_price)) if limit_price is not None else None
        req = ExecutionRequest(
            request_id=f"ER-{uuid4()}",
            idempotency_key=idem,
            purpose=ExecutionPurpose.EXIT,
            source_id=exit_proposal_id,
            broker=broker,
            exchange=position.exchange,
            symbol=position.symbol,
            product=position.product,
            side=side,
            quantity=quantity,
            order_type=OrderType(order_type),
            limit_price=price,
            status=ExecutionRequestStatus.READY,
            created_at=created_at,
            updated_at=created_at,
        )
        self._repository.save_execution_request(req.to_record())
        return req

    @staticmethod
    def _exit_quantity(position: PositionRecord, proposal: ExitProposal) -> int:
        open_qty = abs(position.quantity)
        if proposal.action == ExitAction.EXIT_ALL:
            return open_qty
        if proposal.action == ExitAction.EXIT_QTY:
            qty = int(proposal.requested_quantity or 0)
        else:
            pct = Decimal(proposal.requested_percent or 0)
            qty = int((Decimal(open_qty) * pct / Decimal("100")).to_integral_value(rounding="ROUND_DOWN"))
        if qty <= 0 or qty > open_qty:
            raise ExecutionAuthorizationError("Exit quantity is invalid for current broker exposure")
        return qty
