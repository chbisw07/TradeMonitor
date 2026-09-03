from datetime import UTC, datetime, timedelta

import pytest

from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.enums import (
    AgentVerdict,
    AssetClass,
    ConditionOperator,
    EntryIntentState,
    InstrumentType,
    TradeType,
)
from trademonitor.domain.models import AgentEntryReviewResult, EntryMarketSnapshot, NormalizedTradeIntent, PriceCondition
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


class FixedGateway:
    def __init__(self, verdict, *, reason="reviewed", confidence=80, suggestion=None):
        self.verdict = AgentVerdict(verdict)
        self.reason = reason
        self.confidence = confidence
        self.suggestion = suggestion
        self.calls = []

    def review_entry(self, packet):
        self.calls.append(packet)
        return AgentEntryReviewResult(
            review_id=packet.review_id,
            verdict=self.verdict,
            reason=self.reason,
            confidence=self.confidence,
            suggestion=self.suggestion,
            responded_at=packet.requested_at + timedelta(seconds=1),
        )


class FailingGateway:
    def review_entry(self, packet):
        raise TimeoutError("agents timed out")


def ready_manager(tmp_path):
    repo = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    tm = CoreTMManager(repo)
    tm.start()
    t = datetime(2026, 9, 3, 10, 15, tzinfo=UTC)
    intake = tm.ingest_trade_observation(
        src_id="DS-AG-1",
        source="DAYSCANNER",
        observed_at=t,
        intent=NormalizedTradeIntent(
            underlying="KAYNES", direction="BULLISH", setup="BREAKOUT", trade_type="DAY",
            instrument_type="OPTION", option_type="CE", contract_symbol="KAYNES26SEP4200CE",
            expiry="2026-09-29", strike="4200", premium="145",
        ),
    )
    ti = tm.create_entry_intent(
        episode=intake.episode,
        underlying="KAYNES", direction="BULLISH", trade_type=TradeType.DAY,
        asset_class=AssetClass.EQUITY, instrument_type=InstrumentType.OPTION,
        horizon_at=t + timedelta(hours=5), expiry_date="2026-09-29",
        contract_symbol="KAYNES26SEP4200CE", option_type="CE", strike="4200",
        trigger=PriceCondition(ConditionOperator.ABOVE, "4100"),
        confirmation=PriceCondition(ConditionOperator.ABOVE, "4100"),
        invalidation=PriceCondition(ConditionOperator.BELOW, "4050"),
        premium_min="130", premium_max="160", created_at=t, updated_at=t,
    )
    ready = tm.evaluate_entry_intent(
        ti.entry_intent_id,
        EntryMarketSnapshot(
            observed_at=t + timedelta(minutes=15), spot="4120", premium="150",
            completed_candle_close="4115",
        ),
    )
    assert ready.state == EntryIntentState.READY_FOR_REVIEW
    return tm, ready, t


def test_agent_approve_advances_only_to_ready_for_risk(tmp_path):
    tm, intent, t = ready_manager(tmp_path)
    gateway = FixedGateway(AgentVerdict.APPROVE, suggestion="Optional note only")
    updated = tm.request_entry_agent_review(intent.entry_intent_id, gateway, requested_at=t+timedelta(minutes=16))
    assert updated.state == EntryIntentState.READY_FOR_RISK
    assert len(gateway.calls) == 1
    assert tm.attention_snapshot() == []
    review = tm.entry_review_snapshot(entry_intent_id=intent.entry_intent_id)[0]
    assert review.result.verdict == AgentVerdict.APPROVE
    assert review.result.suggestion == "Optional note only"
    assert not hasattr(updated, "execution_request")


@pytest.mark.parametrize("verdict", [AgentVerdict.REJECT, AgentVerdict.RETREAT_WAIT])
def test_agent_disagreement_escalates_to_user_without_deciding_trade(tmp_path, verdict):
    tm, intent, t = ready_manager(tmp_path)
    updated = tm.request_entry_agent_review(
        intent.entry_intent_id,
        FixedGateway(verdict, reason="independent objection", suggestion="Wait for a cleaner setup"),
        requested_at=t+timedelta(minutes=16),
    )
    assert updated.state == EntryIntentState.USER_DECISION_PENDING
    attention = tm.attention_snapshot()
    assert len(attention) == 1
    assert "APPROVE / REJECT / RETREAT_WAIT" in attention[0].detail
    assert "Wait for a cleaner setup" in attention[0].detail


def test_user_can_approve_after_agent_reject_but_only_to_risk_gate(tmp_path):
    tm, intent, t = ready_manager(tmp_path)
    tm.request_entry_agent_review(intent.entry_intent_id, FixedGateway(AgentVerdict.REJECT), requested_at=t+timedelta(minutes=16))
    resolved = tm.resolve_entry_agent_decision(
        intent.entry_intent_id, AgentVerdict.APPROVE,
        at=t+timedelta(minutes=17), reason="User accepts setup after review",
    )
    assert resolved.state == EntryIntentState.READY_FOR_RISK
    assert tm.attention_snapshot() == []
    review = tm.entry_review_snapshot(entry_intent_id=intent.entry_intent_id)[0]
    assert review.user_decision == AgentVerdict.APPROVE


def test_user_reject_is_terminal_and_user_wait_returns_retreat_wait(tmp_path):
    tm, intent, t = ready_manager(tmp_path)
    tm.request_entry_agent_review(intent.entry_intent_id, FixedGateway(AgentVerdict.REJECT), requested_at=t+timedelta(minutes=16))
    rejected = tm.resolve_entry_agent_decision(
        intent.entry_intent_id, AgentVerdict.REJECT,
        at=t+timedelta(minutes=17), reason="Do not take it",
    )
    assert rejected.state == EntryIntentState.REJECTED
    assert all(x.entry_intent_id != intent.entry_intent_id for x in tm.entry_snapshot())

    # A separate intent demonstrates RETREAT_WAIT semantics.
    tm2, intent2, t2 = ready_manager(tmp_path / "second")
    tm2.request_entry_agent_review(intent2.entry_intent_id, FixedGateway(AgentVerdict.RETREAT_WAIT), requested_at=t2+timedelta(minutes=16))
    waiting = tm2.resolve_entry_agent_decision(
        intent2.entry_intent_id, AgentVerdict.RETREAT_WAIT,
        at=t2+timedelta(minutes=17), reason="Wait for better premium",
    )
    assert waiting.state == EntryIntentState.RETREAT_WAIT


def test_agent_unavailable_escalates_to_user_and_never_implies_approval(tmp_path):
    tm, intent, t = ready_manager(tmp_path)
    updated = tm.request_entry_agent_review(intent.entry_intent_id, FailingGateway(), requested_at=t+timedelta(minutes=16))
    assert updated.state == EntryIntentState.USER_DECISION_PENDING
    review = tm.entry_review_snapshot(entry_intent_id=intent.entry_intent_id)[0]
    assert review.status.value == "FAILED"
    assert review.result is None
    assert "AGENT_UNAVAILABLE" in tm.attention_snapshot()[0].detail


def test_review_states_are_not_reversed_by_market_ticks(tmp_path):
    tm, intent, t = ready_manager(tmp_path)
    approved = tm.request_entry_agent_review(intent.entry_intent_id, FixedGateway(AgentVerdict.APPROVE), requested_at=t+timedelta(minutes=16))
    assert approved.state == EntryIntentState.READY_FOR_RISK
    after_tick = tm.evaluate_entry_intent(
        intent.entry_intent_id,
        EntryMarketSnapshot(observed_at=t+timedelta(minutes=20), spot="4130", premium="151", completed_candle_close="4125"),
    )
    assert after_tick.state == EntryIntentState.READY_FOR_RISK
