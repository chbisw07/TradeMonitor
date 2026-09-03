from datetime import UTC, datetime, timedelta

from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.enums import AgentVerdict, AssetClass, ConditionOperator, EntryIntentState, InstrumentType, TradeType
from trademonitor.domain.models import AgentEntryReviewResult, EntryMarketSnapshot, NormalizedTradeIntent, PriceCondition
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


class RejectGateway:
    def review_entry(self, packet):
        return AgentEntryReviewResult(
            review_id=packet.review_id,
            verdict=AgentVerdict.REJECT,
            reason="Independent review objects",
            confidence=87,
            suggestion="Wait for a pullback",
            responded_at=packet.requested_at + timedelta(seconds=1),
        )


def build(path):
    return CoreTMManager(SQLiteRuntimeRepository(Database(path)))


def test_agent_disagreement_and_user_attention_survive_restart(tmp_path):
    db = tmp_path / "tm.db"
    t = datetime(2026, 9, 3, 10, 15, tzinfo=UTC)
    first = build(db); first.start()
    intake = first.ingest_trade_observation(
        src_id="PS-AG-R", source="POSITIONAL_SCANNER", observed_at=t,
        intent=NormalizedTradeIntent(
            underlying="PNB", direction="BULLISH", setup="BREAKOUT", trade_type="BTST",
            instrument_type="OPTION", option_type="CE", contract_symbol="PNB26SEP117CE",
            expiry="2026-09-29", strike="117", premium="4.85",
        ),
    )
    ti = first.create_entry_intent(
        episode=intake.episode, underlying="PNB", direction="BULLISH",
        trade_type=TradeType.BTST, asset_class=AssetClass.EQUITY, instrument_type=InstrumentType.OPTION,
        horizon_at=t+timedelta(days=1), expiry_date="2026-09-29", contract_symbol="PNB26SEP117CE",
        option_type="CE", strike="117", trigger=PriceCondition(ConditionOperator.ABOVE, "117.79"),
        confirmation=PriceCondition(ConditionOperator.ABOVE, "117.79"), premium_min="4.4", premium_max="5.1",
        created_at=t, updated_at=t,
    )
    first.evaluate_entry_intent(ti.entry_intent_id, EntryMarketSnapshot(
        observed_at=t+timedelta(minutes=15), spot="118.1", premium="4.9", completed_candle_close="118.0"
    ))
    pending = first.request_entry_agent_review(ti.entry_intent_id, RejectGateway(), requested_at=t+timedelta(minutes=16))
    assert pending.state == EntryIntentState.USER_DECISION_PENDING
    first.stop()

    second = build(db); second.start()
    restored = [x for x in second.entry_snapshot() if x.entry_intent_id == ti.entry_intent_id][0]
    assert restored.state == EntryIntentState.USER_DECISION_PENDING
    assert len(second.entry_review_snapshot(entry_intent_id=ti.entry_intent_id)) == 1
    assert any("User decision required" in x.title for x in second.attention_snapshot())
    resolved = second.resolve_entry_agent_decision(
        ti.entry_intent_id, AgentVerdict.RETREAT_WAIT,
        at=t+timedelta(minutes=30), reason="Wait after restart",
    )
    assert resolved.state == EntryIntentState.RETREAT_WAIT
    assert second.attention_snapshot() == []
