"""SEMI_AUTO operator approval boundary for TM4/TGT3."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from uuid import uuid4

from trademonitor.domain.enums import ExecutionApprovalStatus, ExecutionRequestStatus
from trademonitor.domain.events import DomainEvent
from trademonitor.domain.models import ExecutionApproval, ExecutionRequest, utc_now
from trademonitor.persistence.repository import RuntimeRepository


class SemiAutoApprovalError(RuntimeError):
    pass


class SemiAutoApprovalCoordinator:
    """Own durable, explicit User approval for one ready ExecutionRequest.

    Approval is intentionally separate from Risk Management. Risk authorizes the
    exposure; the User confirmation authorizes SEMI_AUTO deployment. A stale
    approval cannot silently grant execution after its TTL.
    """

    def __init__(self, repository: RuntimeRepository, *, ttl_seconds: int = 60) -> None:
        if ttl_seconds <= 0:
            raise ValueError("SEMI_AUTO approval TTL must be positive")
        self._repository = repository
        self._ttl = timedelta(seconds=int(ttl_seconds))

    @property
    def ttl_seconds(self) -> int:
        return int(self._ttl.total_seconds())

    def request(
        self,
        request_id: str,
        *,
        requested_by: str,
        reason: str,
        at: datetime | None = None,
    ) -> tuple[ExecutionApproval, list[DomainEvent]]:
        request = self._require_request(request_id)
        if request.status != ExecutionRequestStatus.READY:
            raise SemiAutoApprovalError("SEMI_AUTO approval requires a READY ExecutionRequest")
        when = at or utc_now()
        latest = self._repository.get_latest_execution_approval(request_id)
        if latest is not None and latest.status == ExecutionApprovalStatus.PENDING:
            return latest, []
        approval = ExecutionApproval(
            approval_id=f"EA-{uuid4()}",
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            status=ExecutionApprovalStatus.PENDING,
            requested_at=when,
            updated_at=when,
            requested_by=requested_by.strip() or "SYSTEM",
            reason=reason.strip() or "SEMI_AUTO execution approval requested",
        )
        self._repository.save_execution_approval(approval.to_record())
        return approval, [self._event("SEMI_AUTO_APPROVAL_REQUESTED", approval)]

    def decide(
        self,
        request_id: str,
        *,
        approve: bool,
        decided_by: str,
        reason: str,
        confirmation: str,
        at: datetime | None = None,
    ) -> tuple[ExecutionApproval, list[DomainEvent]]:
        request = self._require_request(request_id)
        approval = self._repository.get_latest_execution_approval(request_id)
        if approval is None or approval.status != ExecutionApprovalStatus.PENDING:
            raise SemiAutoApprovalError("No pending SEMI_AUTO approval exists for this request")
        if approval.idempotency_key != request.idempotency_key:
            raise SemiAutoApprovalError("Approval does not match current ExecutionRequest identity")
        expected = "APPROVE" if approve else "REJECT"
        if confirmation.strip().upper() != expected:
            raise SemiAutoApprovalError(f"Explicit confirmation must be exactly {expected}")
        when = at or utc_now()
        updated = replace(
            approval,
            status=(ExecutionApprovalStatus.APPROVED if approve else ExecutionApprovalStatus.REJECTED),
            updated_at=when,
            decided_at=when,
            decided_by=decided_by.strip() or "USER",
            decision_reason=reason.strip() or expected,
        )
        self._repository.save_execution_approval(updated.to_record())
        return updated, [self._event(
            "SEMI_AUTO_APPROVAL_APPROVED" if approve else "SEMI_AUTO_APPROVAL_REJECTED", updated
        )]

    def assert_current_approval(self, request: ExecutionRequest, *, at: datetime | None = None) -> ExecutionApproval:
        approval = self._repository.get_latest_execution_approval(request.request_id)
        if approval is None or approval.status != ExecutionApprovalStatus.APPROVED:
            raise SemiAutoApprovalError("Current explicit User approval is required in SEMI_AUTO")
        if approval.idempotency_key != request.idempotency_key:
            raise SemiAutoApprovalError("SEMI_AUTO approval is for a different execution intent")
        now = at or utc_now()
        anchor = approval.decided_at or approval.updated_at
        if now - anchor > self._ttl:
            raise SemiAutoApprovalError(
                f"SEMI_AUTO approval expired after {self.ttl_seconds} seconds; request fresh User approval"
            )
        return approval

    def list(self, *, request_id: str | None = None) -> list[ExecutionApproval]:
        return self._repository.list_execution_approvals(request_id=request_id)

    def _require_request(self, request_id: str) -> ExecutionRequest:
        request = self._repository.get_execution_request(request_id)
        if request is None:
            raise KeyError(f"Unknown execution request: {request_id}")
        return request

    @staticmethod
    def _event(name: str, approval: ExecutionApproval) -> DomainEvent:
        return DomainEvent.create(
            name,
            source="USER" if approval.decided_by else "EXECUTION",
            occurred_at=approval.updated_at,
            payload=approval.to_record(),
        )
