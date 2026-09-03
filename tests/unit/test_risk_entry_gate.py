from datetime import UTC, datetime, timedelta

import pytest

from trademonitor.brokers.mock import MockBroker
from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.enums import (
    AgentVerdict,
    AssetClass,
    ConditionOperator,
    EntryIntentState,
    InstrumentType,
    RiskDecision,
    TradeType,
)
from trademonitor.domain.models import (
    AgentEntryReviewResult,
    BrokerAccountSnapshot,
    BrokerFundsSnapshot,
    BrokerPositionSnapshot,
    EntryMarketSnapshot,
    EntryRiskProposal,
    NormalizedTradeIntent,
    PriceCondition,
)
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


class ApproveGateway:
    def review_entry(self, packet):
        return AgentEntryReviewResult(
            review_id=packet.review_id,
            verdict=AgentVerdict.APPROVE,
            reason="independent validation passed",
            confidence=90,
            responded_at=packet.requested_at + timedelta(seconds=1),
        )


def manager_ready_for_risk(tmp_path, *, reconcile=True, external_position=None):
    repo = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    tm = CoreTMManager(repo)
    tm.start()
    t = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)
    if reconcile:
        positions = [] if external_position is None else [external_position]
        tm.reconcile_broker_truth(
            MockBroker(
                BrokerAccountSnapshot.create(
                    broker="MOCK",
                    positions=positions,
                    funds=BrokerFundsSnapshot.create(
                        available_cash="500000", used_margin="25000", net_value="525000"
                    ),
                    observed_at=t,
                )
            )
        )
    intake = tm.ingest_trade_observation(
        src_id="DS-RISK-1",
        source="DAYSCANNER",
        observed_at=t,
        intent=NormalizedTradeIntent(
            underlying="KAYNES",
            direction="BULLISH",
            setup="BREAKOUT",
            trade_type="DAY",
            instrument_type="OPTION",
            option_type="CE",
            contract_symbol="KAYNES26SEP4200CE",
            expiry="2026-09-29",
            strike="4200",
            premium="145",
        ),
    )
    intent = tm.create_entry_intent(
        episode=intake.episode,
        underlying="KAYNES",
        direction="BULLISH",
        trade_type=TradeType.DAY,
        asset_class=AssetClass.EQUITY,
        instrument_type=InstrumentType.OPTION,
        horizon_at=t + timedelta(hours=5),
        expiry_date="2026-09-29",
        contract_symbol="KAYNES26SEP4200CE",
        option_type="CE",
        strike="4200",
        trigger=PriceCondition(ConditionOperator.ABOVE, "4100"),
        confirmation=PriceCondition(ConditionOperator.ABOVE, "4100"),
        invalidation=PriceCondition(ConditionOperator.BELOW, "4050"),
        premium_min="130",
        premium_max="160",
        created_at=t,
        updated_at=t,
    )
    intent = tm.evaluate_entry_intent(
        intent.entry_intent_id,
        EntryMarketSnapshot(
            observed_at=t + timedelta(minutes=15),
            spot="4120",
            premium="150",
            completed_candle_close="4115",
        ),
    )
    intent = tm.request_entry_agent_review(
        intent.entry_intent_id, ApproveGateway(), requested_at=t + timedelta(minutes=16)
    )
    assert intent.state == EntryIntentState.READY_FOR_RISK
    return tm, repo, intent, t


def proposal(intent, t, *, qty=100, price="150", max_loss="3000"):
    return EntryRiskProposal(
        entry_intent_id=intent.entry_intent_id,
        requested_at=t + timedelta(minutes=17),
        planned_qty=qty,
        planned_entry_price=price,
        planned_max_loss=max_loss,
    )


def test_bootstrap_profile_passes_only_with_current_broker_truth(tmp_path):
    tm, _, intent, t = manager_ready_for_risk(tmp_path)
    decision = tm.evaluate_entry_risk(intent.entry_intent_id, proposal(intent, t))
    assert decision.decision == RiskDecision.PASS
    assert tm.entry_snapshot()[0].state == EntryIntentState.RISK_APPROVED
    assert not hasattr(decision, "execution_request")


def test_missing_broker_truth_is_blocked_and_logged(tmp_path):
    tm, repo, intent, t = manager_ready_for_risk(tmp_path, reconcile=False)
    decision = tm.evaluate_entry_risk(intent.entry_intent_id, proposal(intent, t))
    assert decision.decision == RiskDecision.BLOCK
    assert "BROKER_TRUTH_NOT_CURRENT" in decision.reasons
    assert tm.entry_snapshot()[0].state == EntryIntentState.RISK_BLOCKED
    assert any(e["name"] == "ENTRY_RISK_BLOCKED" for e in repo.list_events())
    assert any("Risk blocked entry" in a.title for a in tm.attention_snapshot())


def test_admin_profile_change_is_two_step_and_blocks_excess_position_value(tmp_path):
    tm, _, intent, t = manager_ready_for_risk(tmp_path)
    original = tm.active_risk_profile()
    change = tm.admin_propose_risk_profile_change(
        reason="Cap PAPER trade exposure for validation",
        requested_at=t + timedelta(minutes=16),
        max_position_value="10000",
    )
    assert tm.active_risk_profile().version == original.version
    with pytest.raises(ValueError):
        tm.admin_confirm_risk_profile_change(change.change_id, confirmation="YES")
    profile = tm.admin_confirm_risk_profile_change(
        change.change_id, confirmation="CONFIRM", confirmed_at=t + timedelta(minutes=16, seconds=30)
    )
    assert profile.version == original.version + 1

    decision = tm.evaluate_entry_risk(
        intent.entry_intent_id,
        proposal(intent, t, qty=100, price="150", max_loss="3000"),
    )
    assert decision.decision == RiskDecision.BLOCK
    assert "MAX_POSITION_VALUE_EXCEEDED" in decision.reasons


def test_configured_max_trade_loss_requires_known_loss_and_enforces_limit(tmp_path):
    tm, _, intent, t = manager_ready_for_risk(tmp_path)
    change = tm.admin_propose_risk_profile_change(
        reason="Validate max trade loss",
        max_trade_loss="2500",
    )
    tm.admin_confirm_risk_profile_change(change.change_id, confirmation="CONFIRM")
    decision = tm.evaluate_entry_risk(
        intent.entry_intent_id,
        proposal(intent, t, max_loss="3000"),
    )
    assert decision.decision == RiskDecision.BLOCK
    assert "MAX_TRADE_LOSS_EXCEEDED" in decision.reasons


def test_unmanaged_external_position_counts_in_portfolio_risk_but_stays_unmanaged(tmp_path):
    external = BrokerPositionSnapshot(
        broker="MOCK",
        broker_position_key="NFO:PNB26SEP117CE:NRML",
        exchange="NFO",
        symbol="PNB26SEP117CE",
        product="NRML",
        quantity=1000,
        average_price="100",
        last_price="110",
    )
    tm, _, intent, t = manager_ready_for_risk(tmp_path, external_position=external)
    assert tm.positions_snapshot(open_only=True)[0].management_status.value == "UNMANAGED"
    change = tm.admin_propose_risk_profile_change(
        reason="Validate portfolio exposure including unmanaged broker truth",
        max_total_exposure="120000",
    )
    tm.admin_confirm_risk_profile_change(change.change_id, confirmation="CONFIRM")
    decision = tm.evaluate_entry_risk(
        intent.entry_intent_id,
        proposal(intent, t, qty=100, price="150", max_loss="2000"),
    )
    assert decision.decision == RiskDecision.BLOCK
    assert "MAX_TOTAL_EXPOSURE_EXCEEDED" in decision.reasons
    assert decision.metrics["unmanaged_open_count"] == 1
    assert tm.positions_snapshot(open_only=True)[0].management_status.value == "UNMANAGED"


def test_max_open_positions_counts_unmanaged_positions(tmp_path):
    external = BrokerPositionSnapshot(
        broker="MOCK",
        broker_position_key="NFO:PNB26SEP117CE:NRML",
        exchange="NFO",
        symbol="PNB26SEP117CE",
        product="NRML",
        quantity=50,
        average_price="5",
        last_price="6",
    )
    tm, _, intent, t = manager_ready_for_risk(tmp_path, external_position=external)
    change = tm.admin_propose_risk_profile_change(
        reason="One open position maximum",
        max_open_positions=1,
    )
    tm.admin_confirm_risk_profile_change(change.change_id, confirmation="CONFIRM")
    decision = tm.evaluate_entry_risk(intent.entry_intent_id, proposal(intent, t))
    assert decision.decision == RiskDecision.BLOCK
    assert "MAX_OPEN_POSITIONS_REACHED" in decision.reasons


def test_profile_and_risk_decision_survive_restart(tmp_path):
    db = tmp_path / "tm.db"
    tm, _, intent, t = manager_ready_for_risk(tmp_path)
    change = tm.admin_propose_risk_profile_change(reason="Persistent risk profile", max_position_value="50000")
    profile = tm.admin_confirm_risk_profile_change(change.change_id, confirmation="CONFIRM")
    decision = tm.evaluate_entry_risk(intent.entry_intent_id, proposal(intent, t))
    tm.stop()

    tm2 = CoreTMManager(SQLiteRuntimeRepository(Database(db)))
    tm2.start()
    assert tm2.active_risk_profile().version == profile.version
    restored = tm2.risk_decision_snapshot(entry_intent_id=intent.entry_intent_id)
    assert len(restored) == 1
    assert restored[0].decision_id == decision.decision_id


def test_risk_block_requires_explicit_rearm_before_new_evaluation(tmp_path):
    tm, _, intent, t = manager_ready_for_risk(tmp_path)
    change = tm.admin_propose_risk_profile_change(reason="Low cap", max_position_value="1000")
    tm.admin_confirm_risk_profile_change(change.change_id, confirmation="CONFIRM")
    first = tm.evaluate_entry_risk(intent.entry_intent_id, proposal(intent, t, qty=100, price="150"))
    assert first.decision == RiskDecision.BLOCK

    change2 = tm.admin_propose_risk_profile_change(reason="Raise cap deliberately", max_position_value="50000")
    tm.admin_confirm_risk_profile_change(change2.change_id, confirmation="CONFIRM")
    with pytest.raises(ValueError):
        tm.evaluate_entry_risk(intent.entry_intent_id, proposal(intent, t, qty=100, price="150"))

    rearmed = tm.rearm_risk_blocked_entry(
        intent.entry_intent_id, at=t + timedelta(minutes=18), reason="Re-evaluate under newly confirmed profile"
    )
    assert rearmed.state == EntryIntentState.READY_FOR_RISK
    second = tm.evaluate_entry_risk(
        intent.entry_intent_id,
        EntryRiskProposal(
            entry_intent_id=intent.entry_intent_id,
            requested_at=t + timedelta(minutes=19),
            planned_qty=100,
            planned_entry_price="150",
            planned_max_loss="3000",
        ),
    )
    assert second.decision == RiskDecision.PASS


def test_persisted_broker_snapshot_is_not_current_risk_truth_after_restart(tmp_path):
    tm, _, intent, t = manager_ready_for_risk(tmp_path)
    entry_id = intent.entry_intent_id
    tm.stop()

    tm2 = CoreTMManager(SQLiteRuntimeRepository(Database(tmp_path / "tm.db")))
    tm2.start()
    # Broker context may retain last-known facts, but current-runtime reconciliation is required.
    decision = tm2.evaluate_entry_risk(
        entry_id,
        EntryRiskProposal(
            entry_intent_id=entry_id,
            requested_at=t + timedelta(minutes=20),
            planned_qty=10,
            planned_entry_price="150",
            planned_max_loss="500",
        ),
    )
    assert decision.decision == RiskDecision.BLOCK
    assert "BROKER_TRUTH_NOT_CURRENT" in decision.reasons
