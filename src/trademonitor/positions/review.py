"""TM3/TGT4 external-Agent strategic-exit validation workflow.

The Position/Exit domain owns the workflow. Agents are an independent service
with lower runtime authority. They may approve, reject, or request retreat/wait
and may add an optional suggestion. They never mutate TM state or execute exits.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from uuid import uuid4

from trademonitor.agents.gateway import AgentGateway
from trademonitor.domain.enums import (
    AgentReviewStatus,
    AgentVerdict,
    ExitProposalClass,
    ExitProposalStatus,
)
from trademonitor.domain.events import DomainEvent
from trademonitor.domain.models import (
    AgentExitReviewPacket,
    ExitProposal,
    ExitReviewRecord,
    utc_now,
)
from trademonitor.persistence.repository import RuntimeRepository
from trademonitor.positions.manager import PositionManager


class ExitReviewError(ValueError):
    pass


class ExitReviewCoordinator:
    """Own Agent-review lifecycle for strategic exit proposals only."""

    def __init__(self, repository: RuntimeRepository, positions: PositionManager) -> None:
        self._repository = repository
        self._positions = positions

    def request_review(
        self,
        exit_proposal_id: str,
        gateway: AgentGateway,
        *,
        requested_at: datetime | None = None,
    ) -> tuple[ExitProposal, ExitReviewRecord, list[DomainEvent]]:
        proposal = self._require_proposal(exit_proposal_id)
        if proposal.proposal_class != ExitProposalClass.STRATEGIC:
            raise ExitReviewError(
                "Agent review is reserved for STRATEGIC/ambiguous exits; "
                "protective and deterministic exits do not wait for Agents"
            )
        if proposal.status != ExitProposalStatus.PENDING:
            raise ExitReviewError("Exit Agent review requires a PENDING strategic proposal")
        latest = self._repository.get_latest_exit_review(exit_proposal_id)
        if latest is not None and latest.user_decision is None:
            raise ExitReviewError("This exit proposal already has an unresolved Agent review")

        position = self._positions.get_position(proposal.position_id)
        if position is None:
            raise ExitReviewError(f"Unknown position: {proposal.position_id}")
        self._positions.require_managed(position)
        if not position.is_open:
            raise ExitReviewError("Cannot review an exit proposal for a closed position")

        at = requested_at or utc_now()
        review_id = f"XR-{uuid4()}"
        packet = AgentExitReviewPacket.from_exit_proposal(
            review_id=review_id,
            requested_at=at,
            proposal=proposal,
            position=position,
            profile=self._positions.management_profile(position.position_id),
        )
        record = ExitReviewRecord(
            review_id=review_id,
            exit_proposal_id=exit_proposal_id,
            packet=packet,
            status=AgentReviewStatus.PENDING,
            created_at=at,
            updated_at=at,
        )
        self._repository.save_exit_review(record.to_record())
        events = [
            self._event(
                "EXIT_AGENT_REVIEW_REQUESTED",
                proposal,
                at,
                review_id=review_id,
                packet=packet.to_record(),
            )
        ]

        try:
            result = gateway.review_exit(packet)
        except Exception as exc:
            failed_at = utc_now()
            failed = replace(record, status=AgentReviewStatus.FAILED, updated_at=failed_at)
            self._repository.save_exit_review(failed.to_record())
            events.extend(
                [
                    self._event(
                        "EXIT_AGENT_REVIEW_FAILED",
                        proposal,
                        failed_at,
                        review_id=review_id,
                        error_type=type(exc).__name__,
                    ),
                    self._event(
                        "EXIT_USER_DECISION_REQUIRED",
                        proposal,
                        failed_at,
                        review_id=review_id,
                        cause="AGENT_UNAVAILABLE",
                    ),
                ]
            )
            return proposal, failed, events

        if result.review_id != review_id:
            failed_at = utc_now()
            failed = replace(record, status=AgentReviewStatus.FAILED, updated_at=failed_at)
            self._repository.save_exit_review(failed.to_record())
            events.extend(
                [
                    self._event(
                        "EXIT_AGENT_REVIEW_FAILED",
                        proposal,
                        failed_at,
                        review_id=review_id,
                        error_type="REVIEW_ID_MISMATCH",
                    ),
                    self._event(
                        "EXIT_USER_DECISION_REQUIRED",
                        proposal,
                        failed_at,
                        review_id=review_id,
                        cause="AGENT_PROTOCOL_FAILURE",
                    ),
                ]
            )
            return proposal, failed, events

        completed_at = result.responded_at
        completed = replace(
            record,
            status=AgentReviewStatus.COMPLETED,
            result=result,
            updated_at=completed_at,
        )
        self._repository.save_exit_review(completed.to_record())
        events.append(
            self._event(
                "EXIT_AGENT_REVIEW_COMPLETED",
                proposal,
                completed_at,
                review_id=review_id,
                verdict=result.verdict.value,
                confidence=result.confidence,
                reason=result.reason,
                suggestion=result.suggestion,
            )
        )

        if result.verdict == AgentVerdict.APPROVE:
            proposal = replace(
                proposal,
                status=ExitProposalStatus.APPROVED,
                updated_at=completed_at,
            )
            self._repository.save_exit_proposal(proposal.to_record())
            events.append(
                self._event("EXIT_AGENT_APPROVED", proposal, completed_at, review_id=review_id)
            )
        else:
            events.append(
                self._event(
                    "EXIT_USER_DECISION_REQUIRED",
                    proposal,
                    completed_at,
                    review_id=review_id,
                    cause=result.verdict.value,
                )
            )
        return proposal, completed, events

    def resolve_user_decision(
        self,
        exit_proposal_id: str,
        decision: AgentVerdict | str,
        *,
        at: datetime,
        reason: str,
    ) -> tuple[ExitProposal, ExitReviewRecord, list[DomainEvent]]:
        proposal = self._require_proposal(exit_proposal_id)
        review = self._repository.get_latest_exit_review(exit_proposal_id)
        if review is None:
            raise ExitReviewError("No Agent review exists for this exit proposal")
        if review.user_decision is not None:
            raise ExitReviewError("User decision has already been recorded")
        if review.status == AgentReviewStatus.COMPLETED and review.result is not None:
            if review.result.verdict == AgentVerdict.APPROVE:
                raise ExitReviewError("Agent APPROVE requires no User escalation")
        # FAILED or completed disagreement both require the User.
        choice = AgentVerdict(decision)
        updated_review = replace(
            review,
            user_decision=choice,
            user_reason=reason,
            updated_at=at,
        )
        self._repository.save_exit_review(updated_review.to_record())

        if choice == AgentVerdict.APPROVE:
            status = ExitProposalStatus.APPROVED
        elif choice == AgentVerdict.REJECT:
            status = ExitProposalStatus.REJECTED
        else:
            status = ExitProposalStatus.RETREAT_WAIT
        proposal = replace(proposal, status=status, updated_at=at)
        self._repository.save_exit_proposal(proposal.to_record())
        return proposal, updated_review, [
            self._event(
                "EXIT_USER_DECISION_RECORDED",
                proposal,
                at,
                review_id=review.review_id,
                decision=choice.value,
                reason=reason,
            )
        ]

    def list_reviews(self, *, exit_proposal_id: str | None = None) -> list[ExitReviewRecord]:
        return self._repository.list_exit_reviews(exit_proposal_id=exit_proposal_id)

    def _require_proposal(self, proposal_id: str) -> ExitProposal:
        proposal = self._repository.get_exit_proposal(proposal_id)
        if proposal is None:
            raise KeyError(f"Unknown exit proposal: {proposal_id}")
        return proposal

    @staticmethod
    def _event(
        name: str, proposal: ExitProposal, at: datetime, **payload
    ) -> DomainEvent:
        return DomainEvent.create(
            name,
            source="EXIT",
            occurred_at=at,
            payload={
                "exit_proposal_id": proposal.proposal_id,
                "position_id": proposal.position_id,
                "proposal_class": proposal.proposal_class.value,
                "action": proposal.action.value,
                "status": proposal.status.value,
                **payload,
            },
        )
