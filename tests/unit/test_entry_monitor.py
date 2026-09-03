from datetime import UTC, datetime, timedelta

import pytest

from trademonitor.candidates.manager import TradeIntakeManager
from trademonitor.domain.enums import (
    AssetClass,
    ConditionOperator,
    EntryIntentState,
    InstrumentType,
    TradeType,
)
from trademonitor.domain.models import EntryIntentRecord, EntryMarketSnapshot, NormalizedTradeIntent, PriceCondition
from trademonitor.entry.monitor import EntryMonitor
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


def setup(tmp_path):
    repo = SQLiteRuntimeRepository(Database(tmp_path / "tm.db")); repo.initialize()
    intake = TradeIntakeManager(repo)
    observed = datetime(2026, 9, 3, 10, 15, tzinfo=UTC)
    result, _ = intake.ingest(
        src_id="PS-1", source="POSITIONAL_SCANNER", observed_at=observed,
        intent=NormalizedTradeIntent(
            underlying="PNB", direction="BULLISH", setup="BREAKOUT", trade_type="BTST",
            instrument_type="OPTION", option_type="CE", contract_symbol="PNB26SEP117CE",
            expiry="2026-09-29", strike="117", premium="4.85",
        ),
    )
    return EntryMonitor(repo), repo, result.episode, observed


def make_intent(episode_id, t, **overrides):
    data = dict(
        entry_intent_id="TI-1", episode_id=episode_id, underlying="PNB", direction="BULLISH",
        trade_type=TradeType.BTST, asset_class=AssetClass.EQUITY,
        instrument_type=InstrumentType.OPTION, horizon_at=t + timedelta(days=1),
        expiry_date="2026-09-29", contract_symbol="PNB26SEP117CE", option_type="CE", strike="117",
        trigger=PriceCondition(ConditionOperator.ABOVE, "117.79"),
        confirmation=PriceCondition(ConditionOperator.ABOVE, "117.79"),
        invalidation=PriceCondition(ConditionOperator.BELOW, "116.27"),
        premium_min="4.40", premium_max="5.10",
        created_at=t, updated_at=t,
    )
    data.update(overrides)
    return EntryIntentRecord(**data)


def test_trigger_then_waits_for_completed_candle_confirmation(tmp_path):
    monitor, _, episode, t = setup(tmp_path)
    intent, _ = monitor.create_intent(make_intent(episode.episode_id, t))
    state, events = monitor.evaluate(intent.entry_intent_id, EntryMarketSnapshot(observed_at=t+timedelta(minutes=2), spot="118.05", premium="4.80"))
    assert state.state == EntryIntentState.CONFIRMING
    assert [e.payload["state"] for e in events] == ["TRIGGERED", "CONFIRMING"]


def test_confirmation_and_current_premium_revalidation_make_ready_for_review(tmp_path):
    monitor, _, episode, t = setup(tmp_path)
    intent, _ = monitor.create_intent(make_intent(episode.episode_id, t))
    ready, _ = monitor.evaluate(intent.entry_intent_id, EntryMarketSnapshot(
        observed_at=t+timedelta(minutes=15), spot="118.10", premium="4.90", completed_candle_close="118.02"
    ))
    assert ready.state == EntryIntentState.READY_FOR_REVIEW
    assert "revalidation passed" in ready.last_reason


def test_failed_confirmation_retreats_and_requires_explicit_rearm(tmp_path):
    monitor, _, episode, t = setup(tmp_path)
    intent, _ = monitor.create_intent(make_intent(episode.episode_id, t))
    waiting, _ = monitor.evaluate(intent.entry_intent_id, EntryMarketSnapshot(
        observed_at=t+timedelta(minutes=15), spot="118.10", premium="4.90", completed_candle_close="117.60"
    ))
    assert waiting.state == EntryIntentState.RETREAT_WAIT
    unchanged, events = monitor.evaluate(intent.entry_intent_id, EntryMarketSnapshot(
        observed_at=t+timedelta(minutes=20), spot="118.20", premium="4.90", completed_candle_close="118.10"
    ))
    assert unchanged.state == EntryIntentState.RETREAT_WAIT and events == []
    rearmed, _ = monitor.rearm(intent.entry_intent_id, at=t+timedelta(minutes=21), reason="Fresh breakout cycle")
    assert rearmed.state == EntryIntentState.MONITORING


def test_underlying_invalidation_terminates_entry_intent(tmp_path):
    monitor, _, episode, t = setup(tmp_path)
    intent, _ = monitor.create_intent(make_intent(episode.episode_id, t))
    invalid, _ = monitor.evaluate(intent.entry_intent_id, EntryMarketSnapshot(observed_at=t+timedelta(minutes=5), spot="116.00", premium="3.90"))
    assert invalid.state == EntryIntentState.INVALIDATED
    assert monitor.list_active() == []


def test_horizon_expiry_precedes_entry_logic(tmp_path):
    monitor, _, episode, t = setup(tmp_path)
    intent, _ = monitor.create_intent(make_intent(episode.episode_id, t, horizon_at=t+timedelta(minutes=30)))
    expired, _ = monitor.evaluate(intent.entry_intent_id, EntryMarketSnapshot(observed_at=t+timedelta(minutes=31), spot="119", premium="5"))
    assert expired.state == EntryIntentState.EXPIRED


def test_stretched_premium_causes_retreat_wait_not_chase(tmp_path):
    monitor, _, episode, t = setup(tmp_path)
    intent, _ = monitor.create_intent(make_intent(episode.episode_id, t))
    waiting, _ = monitor.evaluate(intent.entry_intent_id, EntryMarketSnapshot(
        observed_at=t+timedelta(minutes=15), spot="118.10", premium="5.80", completed_candle_close="118.00"
    ))
    assert waiting.state == EntryIntentState.RETREAT_WAIT
    assert "do not chase" in waiting.last_reason


@pytest.mark.parametrize("trade_type", list(TradeType))
def test_all_frozen_trade_types_are_supported(tmp_path, trade_type):
    _, _, episode, t = setup(tmp_path)
    record = make_intent(episode.episode_id, t, trade_type=trade_type)
    assert record.trade_type == trade_type


def test_fno_requires_expiry_and_horizon_cannot_exceed_it(tmp_path):
    _, _, episode, t = setup(tmp_path)
    with pytest.raises(ValueError, match="require expiry_date"):
        make_intent(episode.episode_id, t, expiry_date=None)
    with pytest.raises(ValueError, match="cannot extend beyond"):
        make_intent(episode.episode_id, t, horizon_at=datetime(2026, 10, 1, tzinfo=UTC))


def test_cash_is_future_compatible_without_expiry(tmp_path):
    _, _, episode, t = setup(tmp_path)
    record = make_intent(
        episode.episode_id, t, instrument_type=InstrumentType.CASH, expiry_date=None,
        contract_symbol="PNB", option_type=None, strike=None,
    )
    assert record.instrument_type == InstrumentType.CASH and record.expiry_date is None
