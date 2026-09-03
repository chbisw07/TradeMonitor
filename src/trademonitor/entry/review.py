"""TM2/TGT3 external-Agent entry validation workflow.

The Entry domain owns the workflow. Agents are an independent service with lower
runtime authority. They may approve, reject, or ask to retreat/wait and may add
an optional suggestion. They never mutate TradeMonitor state or execute trades.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from uuid import uuid4

from trademonitor.agents.gateway import AgentGateway
from trademonitor.domain.enums import AgentReviewStatus, AgentVerdict, EntryIntentState
from trademonitor.domain.events import DomainEvent
from trademonitor.domain.models import (
    AgentEntryReviewPacket,
    AgentEntryReviewResult,
    EntryIntentRecord,
    EntryReviewRecord,
    utc_now,
)
from trademonitor.persistence.repository import RuntimeRepository


class EntryReviewCoordinator:
    """Own Agent-review lifecycle for entry intents; no Risk/Execution logic."""

    def __init__(self, repository: RuntimeRepository) -> None:
        self._repository = repository

    def request_review(
        self,
        entry_intent_id: str,
        gateway: AgentGateway,
        *,
        requested_at: datetime | None = None,
    ) -> tuple[EntryIntentRecord, EntryReviewRecord, list[DomainEvent]]:
        intent = self._require_intent(entry_intent_id)
        if intent.state != EntryIntentState.READY_FOR_REVIEW:
            raise ValueError("Agent review requires READY_FOR_REVIEW entry intent")

        at = requested_at or utc_now()
        review_id = f"AR-{uuid4()}"
        packet = AgentEntryReviewPacket.from_entry_intent(
            review_id=review_id, requested_at=at, intent=intent
        )
        record = EntryReviewRecord(
            review_id=review_id,
            entry_intent_id=entry_intent_id,
            packet=packet,
            status=AgentReviewStatus.PENDING,
            created_at=at,
            updated_at=at,
        )
        self._repository.save_entry_review(record.to_record())
        intent = self._set_state(
            intent,
            EntryIntentState.AGENT_REVIEW_PENDING,
            at,
            "External Agents review requested",
        )
        events = [
            self._event(
                "ENTRY_AGENT_REVIEW_REQUESTED",
                intent,
                review_id=review_id,
                packet=packet.to_record(),
            )
        ]

        try:
            result = gateway.review_entry(packet)
        except Exception as exc:
            failed_at = utc_now()
            failed = replace(
                record,
                status=AgentReviewStatus.FAILED,
                updated_at=failed_at,
            )
            self._repository.save_entry_review(failed.to_record())
            intent = self._set_state(
                intent,
                EntryIntentState.USER_DECISION_PENDING,
                failed_at,
                "Agents unavailable; User decision required",
            )
            events.extend(
                [
                    self._event(
                        "ENTRY_AGENT_REVIEW_FAILED",
                        intent,
                        review_id=review_id,
                        error_type=type(exc).__name__,
                    ),
                    self._event(
                        "ENTRY_USER_DECISION_REQUIRED",
                        intent,
                        review_id=review_id,
                        cause="AGENT_UNAVAILABLE",
                    ),
                ]
            )
            return intent, failed, events

        if result.review_id != review_id:
            failed_at = utc_now()
            failed = replace(record, status=AgentReviewStatus.FAILED, updated_at=failed_at)
            self._repository.save_entry_review(failed.to_record())
            intent = self._set_state(
                intent,
                EntryIntentState.USER_DECISION_PENDING,
                failed_at,
                "Invalid Agents response correlation; User decision required",
            )
            events.extend(
                [
                    self._event(
                        "ENTRY_AGENT_REVIEW_FAILED",
                        intent,
                        review_id=review_id,
                        error_type="REVIEW_ID_MISMATCH",
                    ),
                    self._event(
                        "ENTRY_USER_DECISION_REQUIRED",
                        intent,
                        review_id=review_id,
                        cause="AGENT_PROTOCOL_FAILURE",
                    ),
                ]
            )
            return intent, failed, events

        completed_at = result.responded_at
        completed = replace(
            record,
            status=AgentReviewStatus.COMPLETED,
            result=result,
            updated_at=completed_at,
        )
        self._repository.save_entry_review(completed.to_record())
        events.append(
            self._event(
                "ENTRY_AGENT_REVIEW_COMPLETED",
                intent,
                review_id=review_id,
                verdict=result.verdict.value,
                confidence=result.confidence,
                reason=result.reason,
                suggestion=result.suggestion,
            )
        )

        if result.verdict == AgentVerdict.APPROVE:
            intent = self._set_state(
                intent,
                EntryIntentState.READY_FOR_RISK,
                completed_at,
                "Agents approved entry; ready for Risk Management gate",
            )
            events.append(
                self._event("ENTRY_AGENT_APPROVED", intent, review_id=review_id)
            )
        else:
            intent = self._set_state(
                intent,
                EntryIntentState.USER_DECISION_PENDING,
                completed_at,
                f"Agents verdict {result.verdict.value}; User decision required",
            )
            events.append(
                self._event(
                    "ENTRY_USER_DECISION_REQUIRED",
                    intent,
                    review_id=review_id,
                    cause=result.verdict.value,
                )
            )
        return intent, completed, events

    def resolve_user_decision(
        self,
        entry_intent_id: str,
        decision: AgentVerdict | str,
        *,
        at: datetime,
        reason: str,
    ) -> tuple[EntryIntentRecord, EntryReviewRecord, list[DomainEvent]]:
        intent = self._require_intent(entry_intent_id)
        if intent.state != EntryIntentState.USER_DECISION_PENDING:
            raise ValueError("User resolution requires USER_DECISION_PENDING")
        review = self._repository.get_latest_entry_review(entry_intent_id)
        if review is None:
            raise RuntimeError("No Agent review exists for pending User decision")

        choice = AgentVerdict(decision)
        updated_review = replace(
            review,
            user_decision=choice,
            user_reason=reason,
            updated_at=at,
        )
        self._repository.save_entry_review(updated_review.to_record())

        if choice == AgentVerdict.APPROVE:
            state = EntryIntentState.READY_FOR_RISK
            state_reason = "User approved after Agent disagreement/unavailability"
        elif choice == AgentVerdict.REJECT:
            state = EntryIntentState.REJECTED
            state_reason = "User rejected entry after Agent review"
        else:
            state = EntryIntentState.RETREAT_WAIT
            state_reason = "User chose RETREAT_WAIT after Agent review"

        intent = self._set_state(intent, state, at, state_reason)
        return intent, updated_review, [
            self._event(
                "ENTRY_USER_DECISION_RECORDED",
                intent,
                review_id=review.review_id,
                decision=choice.value,
                reason=reason,
            )
        ]

    def list_reviews(self, *, entry_intent_id: str | None = None) -> list[EntryReviewRecord]:
        return self._repository.list_entry_reviews(entry_intent_id=entry_intent_id)

    def _require_intent(self, entry_intent_id: str) -> EntryIntentRecord:
        intent = self._repository.get_entry_intent(entry_intent_id)
        if intent is None:
            raise KeyError(f"Unknown entry intent: {entry_intent_id}")
        return intent

    def _set_state(
        self,
        intent: EntryIntentRecord,
        state: EntryIntentState,
        at: datetime,
        reason: str,
    ) -> EntryIntentRecord:
        updated = replace(intent, state=state, updated_at=at, last_reason=reason)
        self._repository.save_entry_intent(updated.to_record())
        return updated

    @staticmethod
    def _event(name: str, intent: EntryIntentRecord, **payload) -> DomainEvent:
        return DomainEvent.create(
            name,
            source="ENTRY",
            occurred_at=intent.updated_at,
            payload={
                "entry_intent_id": intent.entry_intent_id,
                "episode_id": intent.episode_id,
                "state": intent.state.value,
                **payload,
            },
        )
