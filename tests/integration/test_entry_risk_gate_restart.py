from datetime import UTC, datetime, timedelta

from trademonitor.brokers.mock import MockBroker
from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.enums import AgentVerdict, AssetClass, ConditionOperator, EntryIntentState, InstrumentType, TradeType
from trademonitor.domain.models import AgentEntryReviewResult, BrokerAccountSnapshot, EntryMarketSnapshot, EntryRiskProposal, NormalizedTradeIntent, PriceCondition
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


class Approve:
    def review_entry(self, packet):
        return AgentEntryReviewResult(review_id=packet.review_id, verdict=AgentVerdict.APPROVE, reason="ok", responded_at=packet.requested_at)


def test_risk_block_is_durable_and_does_not_auto_reawaken_after_profile_change(tmp_path):
    db = tmp_path / "tm.db"
    tm = CoreTMManager(SQLiteRuntimeRepository(Database(db)))
    tm.start()
    t = datetime(2026, 9, 4, 11, 0, tzinfo=UTC)
    tm.reconcile_broker_truth(MockBroker(BrokerAccountSnapshot.create(broker="MOCK", observed_at=t)))
    intake = tm.ingest_trade_observation(src_id="X", source="USER", observed_at=t, intent=NormalizedTradeIntent(underlying="PNB", direction="BULLISH", setup="BREAKOUT", trade_type="DAY", instrument_type="OPTION", option_type="CE", contract_symbol="PNB26SEP117CE", expiry="2026-09-29", strike="117"))
    intent = tm.create_entry_intent(episode=intake.episode, underlying="PNB", direction="BULLISH", trade_type=TradeType.DAY, asset_class=AssetClass.EQUITY, instrument_type=InstrumentType.OPTION, horizon_at=t+timedelta(hours=4), expiry_date="2026-09-29", contract_symbol="PNB26SEP117CE", option_type="CE", strike="117", trigger=PriceCondition(ConditionOperator.ABOVE,"117"), created_at=t, updated_at=t)
    intent = tm.evaluate_entry_intent(intent.entry_intent_id, EntryMarketSnapshot(observed_at=t+timedelta(minutes=1), spot="118", premium="5"))
    intent = tm.request_entry_agent_review(intent.entry_intent_id, Approve(), requested_at=t+timedelta(minutes=2))
    change = tm.admin_propose_risk_profile_change(reason="Small cap", max_position_value="1000")
    tm.admin_confirm_risk_profile_change(change.change_id, confirmation="CONFIRM")
    result = tm.evaluate_entry_risk(intent.entry_intent_id, EntryRiskProposal(entry_intent_id=intent.entry_intent_id, requested_at=t+timedelta(minutes=3), planned_qty=1000, planned_entry_price="5", planned_max_loss="1000"))
    assert result.decision.value == "BLOCK"
    tm.stop()

    tm2 = CoreTMManager(SQLiteRuntimeRepository(Database(db)))
    tm2.start()
    restored = [x for x in tm2.entry_snapshot() if x.entry_intent_id == intent.entry_intent_id][0]
    assert restored.state == EntryIntentState.RISK_BLOCKED
    # A later Admin profile change does not silently resurrect or execute the blocked trade.
    change2 = tm2.admin_propose_risk_profile_change(reason="Larger cap", max_position_value="10000")
    tm2.admin_confirm_risk_profile_change(change2.change_id, confirmation="CONFIRM")
    still_blocked = [x for x in tm2.entry_snapshot() if x.entry_intent_id == intent.entry_intent_id][0]
    assert still_blocked.state == EntryIntentState.RISK_BLOCKED
