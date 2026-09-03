"""TM2/TGT2 entry monitoring and trade-intent lifecycle.

This domain converts an accepted time-relevant Episode into a monitored trade
intent. It does not consult Agents, make Risk decisions, create execution
requests, or write to a broker.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from typing import Iterable
from uuid import uuid4

from trademonitor.domain.enums import EntryIntentState
from trademonitor.domain.events import DomainEvent
from trademonitor.domain.models import EntryIntentRecord, EntryMarketSnapshot, EpisodeRecord
from trademonitor.persistence.repository import RuntimeRepository


class EntryMonitor:
    """Own deterministic trigger/confirmation/revalidation for entry intents."""

    def __init__(self, repository: RuntimeRepository) -> None:
        self._repository = repository

    def create_intent(self, intent: EntryIntentRecord) -> tuple[EntryIntentRecord, list[DomainEvent]]:
        if self._repository.get_entry_intent(intent.entry_intent_id) is not None:
            raise ValueError(f"Entry intent already exists: {intent.entry_intent_id}")
        existing = self._repository.get_active_entry_intent_for_episode(intent.episode_id)
        if existing is not None:
            return existing, [self._event("ENTRY_INTENT_ALREADY_ACTIVE", existing, "Episode already has active entry intent")]
        self._repository.save_entry_intent(intent.to_record())
        return intent, [self._event("ENTRY_INTENT_CREATED", intent, "Entry intent admitted to monitoring")]

    def create_for_episode(self, *, episode: EpisodeRecord, **kwargs) -> tuple[EntryIntentRecord, list[DomainEvent]]:
        return self.create_intent(EntryIntentRecord(entry_intent_id=f"TI-{uuid4()}", episode_id=episode.episode_id, **kwargs))

    def evaluate(
        self,
        entry_intent_id: str,
        snapshot: EntryMarketSnapshot,
    ) -> tuple[EntryIntentRecord, list[DomainEvent]]:
        current = self._require(entry_intent_id)
        if current.state in {
            EntryIntentState.REJECTED,
            EntryIntentState.INVALIDATED,
            EntryIntentState.EXPIRED,
            EntryIntentState.CANCELLED,
        }:
            return current, []

        # Review/Risk handoff states are owned by later gates; market ticks must not
        # silently move them back into entry monitoring.
        if current.state in {
            EntryIntentState.AGENT_REVIEW_PENDING,
            EntryIntentState.USER_DECISION_PENDING,
            EntryIntentState.READY_FOR_RISK,
            EntryIntentState.RISK_APPROVED,
            EntryIntentState.RISK_BLOCKED,
        }:
            return current, []

        # Time/contract boundaries are checked before price logic.
        if snapshot.observed_at > current.horizon_at:
            return self._transition(current, EntryIntentState.EXPIRED, snapshot, "Trade horizon reached")
        if current.expiry_date is not None and snapshot.observed_at.date() > current.expiry_date:
            return self._transition(current, EntryIntentState.EXPIRED, snapshot, "F&O contract expiry passed")

        if current.invalidation is not None and current.invalidation.matches(snapshot.spot):
            return self._transition(current, EntryIntentState.INVALIDATED, snapshot, "Underlying invalidation condition met")

        # RETREAT_WAIT is deliberately sticky until the owning entry workflow rearms it.
        if current.state == EntryIntentState.RETREAT_WAIT:
            return current, []

        if not current.trigger.matches(snapshot.spot):
            if current.state != EntryIntentState.MONITORING:
                return self._transition(current, EntryIntentState.MONITORING, snapshot, "Trigger no longer valid")
            return self._touch(current, snapshot), []

        events: list[DomainEvent] = []
        working = current
        if working.state == EntryIntentState.MONITORING:
            working, ev = self._transition(working, EntryIntentState.TRIGGERED, snapshot, "Entry trigger detected")
            events.extend(ev)

        if working.confirmation is not None:
            if snapshot.completed_candle_close is None:
                if working.state != EntryIntentState.CONFIRMING:
                    working, ev = self._transition(working, EntryIntentState.CONFIRMING, snapshot, "Awaiting completed candle confirmation")
                    events.extend(ev)
                return working, events
            if not working.confirmation.matches(snapshot.completed_candle_close):
                working, ev = self._transition(working, EntryIntentState.RETREAT_WAIT, snapshot, "Completed candle confirmation failed")
                events.extend(ev)
                return working, events

        # Final lightweight current-market revalidation before handing to TGT3 review.
        if working.premium_min is not None or working.premium_max is not None:
            if snapshot.premium is None:
                working, ev = self._transition(working, EntryIntentState.RETREAT_WAIT, snapshot, "Current contract premium unavailable for revalidation")
                events.extend(ev)
                return working, events
            if working.premium_min is not None and snapshot.premium < working.premium_min:
                working, ev = self._transition(working, EntryIntentState.RETREAT_WAIT, snapshot, "Premium below permitted entry zone")
                events.extend(ev)
                return working, events
            if working.premium_max is not None and snapshot.premium > working.premium_max:
                working, ev = self._transition(working, EntryIntentState.RETREAT_WAIT, snapshot, "Premium above permitted entry zone; do not chase")
                events.extend(ev)
                return working, events

        if working.state != EntryIntentState.READY_FOR_REVIEW:
            working, ev = self._transition(working, EntryIntentState.READY_FOR_REVIEW, snapshot, "Trigger, confirmation and current-market revalidation passed")
            events.extend(ev)
        return working, events

    def rearm(self, entry_intent_id: str, *, at: datetime, reason: str) -> tuple[EntryIntentRecord, list[DomainEvent]]:
        current = self._require(entry_intent_id)
        if current.state != EntryIntentState.RETREAT_WAIT:
            raise ValueError("Only RETREAT_WAIT entry intents may be rearmed")
        updated = replace(current, state=EntryIntentState.MONITORING, updated_at=at, last_reason=reason)
        self._repository.save_entry_intent(updated.to_record())
        return updated, [self._event("ENTRY_INTENT_REARMED", updated, reason)]

    def cancel(self, entry_intent_id: str, *, at: datetime, reason: str) -> tuple[EntryIntentRecord, list[DomainEvent]]:
        current = self._require(entry_intent_id)
        updated = replace(current, state=EntryIntentState.CANCELLED, updated_at=at, last_reason=reason)
        self._repository.save_entry_intent(updated.to_record())
        return updated, [self._event("ENTRY_INTENT_CANCELLED", updated, reason)]

    def get(self, entry_intent_id: str) -> EntryIntentRecord | None:
        return self._repository.get_entry_intent(entry_intent_id)

    def list_active(self) -> list[EntryIntentRecord]:
        return self._repository.list_entry_intents(active_only=True)

    def _require(self, entry_intent_id: str) -> EntryIntentRecord:
        current = self._repository.get_entry_intent(entry_intent_id)
        if current is None:
            raise KeyError(f"Unknown entry intent: {entry_intent_id}")
        return current

    def _touch(self, current: EntryIntentRecord, snapshot: EntryMarketSnapshot) -> EntryIntentRecord:
        updated = replace(current, updated_at=snapshot.observed_at, last_spot=snapshot.spot, last_premium=snapshot.premium)
        self._repository.save_entry_intent(updated.to_record())
        return updated

    def _transition(self, current: EntryIntentRecord, state: EntryIntentState, snapshot: EntryMarketSnapshot, reason: str):
        updated = replace(
            current,
            state=state,
            updated_at=snapshot.observed_at,
            last_spot=snapshot.spot,
            last_premium=snapshot.premium,
            last_reason=reason,
        )
        self._repository.save_entry_intent(updated.to_record())
        return updated, [self._event("ENTRY_INTENT_STATE_CHANGED", updated, reason, previous=current.state.value)]

    @staticmethod
    def _event(name: str, intent: EntryIntentRecord, reason: str, **extra) -> DomainEvent:
        return DomainEvent.create(
            name,
            source="ENTRY",
            occurred_at=intent.updated_at,
            payload={
                "entry_intent_id": intent.entry_intent_id,
                "episode_id": intent.episode_id,
                "state": intent.state.value,
                "trade_type": intent.trade_type.value,
                "reason": reason,
                **extra,
            },
        )
