from datetime import UTC, datetime, timedelta

from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.enums import AssetClass, ConditionOperator, EntryIntentState, InstrumentType, TradeType
from trademonitor.domain.models import EntryMarketSnapshot, NormalizedTradeIntent, PriceCondition
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


def build(path):
    return CoreTMManager(SQLiteRuntimeRepository(Database(path)))


def test_entry_intent_survives_restart_and_continues_monitoring(tmp_path):
    db = tmp_path / "tm.db"
    t = datetime(2026, 9, 3, 10, 15, tzinfo=UTC)
    first = build(db); first.start()
    intake = first.ingest_trade_observation(
        src_id="DS-1", source="DAYSCANNER", observed_at=t,
        intent=NormalizedTradeIntent(
            underlying="KAYNES", direction="BULLISH", setup="BREAKOUT", trade_type="DAY",
            instrument_type="OPTION", option_type="CE", contract_symbol="KAYNES26SEP4200CE",
            expiry="2026-09-29", strike="4200", premium="145",
        ),
    )
    ti = first.create_entry_intent(
        episode=intake.episode, underlying="KAYNES", direction="BULLISH",
        trade_type=TradeType.DAY, asset_class=AssetClass.EQUITY, instrument_type=InstrumentType.OPTION,
        horizon_at=t+timedelta(hours=5), expiry_date="2026-09-29", contract_symbol="KAYNES26SEP4200CE",
        option_type="CE", strike="4200", trigger=PriceCondition(ConditionOperator.ABOVE, "4100"),
        confirmation=PriceCondition(ConditionOperator.ABOVE, "4100"), premium_min="130", premium_max="160",
        created_at=t, updated_at=t,
    )
    confirming = first.evaluate_entry_intent(ti.entry_intent_id, EntryMarketSnapshot(observed_at=t+timedelta(minutes=5), spot="4110", premium="145"))
    assert confirming.state == EntryIntentState.CONFIRMING
    first.stop()

    second = build(db); second.start()
    restored = second.entry_snapshot()
    assert len(restored) == 1 and restored[0].state == EntryIntentState.CONFIRMING
    ready = second.evaluate_entry_intent(ti.entry_intent_id, EntryMarketSnapshot(
        observed_at=t+timedelta(minutes=15), spot="4120", premium="150", completed_candle_close="4115"
    ))
    assert ready.state == EntryIntentState.READY_FOR_REVIEW
    assert second.contexts.get("trade").data["entry_monitoring"]["by_state"] == {"READY_FOR_REVIEW": 1}
    second.stop()
