from datetime import UTC, datetime, timedelta
from threading import Thread

import pytest

from trademonitor.brokers.execution_simulator import SimulatedExecutionBroker, SubmitFault
from trademonitor.brokers.mock import MockBroker
from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.enums import (
    AgentVerdict, AssetClass, BrokerOrderStatus, ConditionOperator,
    EntryIntentState, ExecutionRequestStatus, InstrumentType, OrderSide,
    OrderType, TradeType,
)
from trademonitor.domain.models import (
    AgentEntryReviewResult, BrokerAccountSnapshot, EntryMarketSnapshot,
    EntryRiskProposal, NormalizedTradeIntent, PriceCondition,
)
from trademonitor.execution.requests import ExecutionAuthorizationError
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


class _ApproveGateway:
    def review_entry(self, packet):
        return AgentEntryReviewResult(
            review_id=packet.review_id,
            verdict=AgentVerdict.APPROVE,
            reason="ok",
            confidence=90,
            responded_at=packet.requested_at + timedelta(seconds=1),
        )


def _approved_entry(workdir, *, db_name="tm.db"):
    repo = SQLiteRuntimeRepository(Database(workdir / db_name))
    tm = CoreTMManager(repo); tm.start()
    t = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)
    tm.reconcile_broker_truth(MockBroker(BrokerAccountSnapshot.create(broker="SIM", observed_at=t), name="SIM"))
    intake = tm.ingest_trade_observation(
        src_id="X", source="TEST", observed_at=t,
        intent=NormalizedTradeIntent(
            underlying="KAYNES", direction="BULLISH", setup="BREAKOUT",
            trade_type="DAY", instrument_type="OPTION", option_type="CE",
            contract_symbol="KAYNES26SEP4200CE", expiry="2026-09-29",
            strike="4200", premium="145",
        ),
    )
    intent = tm.create_entry_intent(
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
    tm.evaluate_entry_intent(
        intent.entry_intent_id,
        EntryMarketSnapshot(
            observed_at=t + timedelta(minutes=15), spot="4120", premium="150",
            completed_candle_close="4115"
        ),
    )
    intent = tm.request_entry_agent_review(
        intent.entry_intent_id, _ApproveGateway(), requested_at=t + timedelta(minutes=16)
    )
    decision = tm.evaluate_entry_risk(
        intent.entry_intent_id,
        EntryRiskProposal(
            entry_intent_id=intent.entry_intent_id,
            requested_at=t + timedelta(minutes=17), planned_qty=100,
            planned_entry_price="150", planned_max_loss="3000",
        ),
    )
    assert tm.entry_snapshot()[0].state == EntryIntentState.RISK_APPROVED
    request = tm.prepare_entry_execution_request(
        entry_intent_id=intent.entry_intent_id,
        risk_decision_id=decision.decision_id,
        broker="SIM", exchange="NFO", product="NRML",
        side=OrderSide.BUY, order_type=OrderType.LIMIT,
        created_at=t + timedelta(minutes=18),
    )
    return tm, request, t


def test_crash_after_broker_accept_before_ack_recovers_without_resubmit(tmp_path):
    tm, request, _ = _approved_entry(tmp_path)
    broker = SimulatedExecutionBroker(name="SIM")
    broker.queue_submit_fault(SubmitFault.ACCEPT_THEN_TIMEOUT)
    uncertain = tm.deploy_execution_request(request.request_id, broker)
    assert uncertain.status == ExecutionRequestStatus.UNCERTAIN
    assert broker.submit_count == 1
    tm.stop()

    tm2 = CoreTMManager(SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))); tm2.start()
    recovered = tm2.reconcile_execution_request(request.request_id, broker)
    assert recovered.status == ExecutionRequestStatus.SUBMITTED
    assert broker.submit_count == 1


def test_disconnect_before_accept_stays_uncertain_and_never_blind_retries(tmp_path):
    tm, request, _ = _approved_entry(tmp_path)
    broker = SimulatedExecutionBroker(name="SIM")
    broker.queue_submit_fault(SubmitFault.DISCONNECT_BEFORE_ACCEPT)
    first = tm.deploy_execution_request(request.request_id, broker)
    assert first.status == ExecutionRequestStatus.UNCERTAIN
    second = tm.deploy_execution_request(request.request_id, broker)
    assert second.status == ExecutionRequestStatus.UNCERTAIN
    assert broker.submit_count == 1
    assert broker.order_for_client(request.idempotency_key) is None


def test_broker_reconciliation_delay_converges_when_truth_becomes_visible(tmp_path):
    tm, request, _ = _approved_entry(tmp_path)
    broker = SimulatedExecutionBroker(name="SIM")
    broker.queue_submit_fault(SubmitFault.ACCEPT_THEN_TIMEOUT)
    tm.deploy_execution_request(request.request_id, broker)
    broker.delay_client_visibility(request.idempotency_key, fetches=2)
    assert tm.reconcile_execution_request(request.request_id, broker).status == ExecutionRequestStatus.UNCERTAIN
    assert tm.reconcile_execution_request(request.request_id, broker).status == ExecutionRequestStatus.UNCERTAIN
    resolved = tm.reconcile_execution_request(request.request_id, broker)
    assert resolved.status == ExecutionRequestStatus.SUBMITTED
    assert broker.submit_count == 1


def test_reconciliation_disconnect_is_contained_as_uncertain_then_recovers(tmp_path):
    tm, request, _ = _approved_entry(tmp_path)
    broker = SimulatedExecutionBroker(name="SIM")
    submitted = tm.deploy_execution_request(request.request_id, broker)
    assert submitted.status == ExecutionRequestStatus.SUBMITTED
    broker.fail_next_fetches(1)
    assert tm.reconcile_execution_request(request.request_id, broker).status == ExecutionRequestStatus.UNCERTAIN
    assert tm.reconcile_execution_request(request.request_id, broker).status == ExecutionRequestStatus.SUBMITTED


def test_partial_fill_then_fill_survives_restart(tmp_path):
    tm, request, _ = _approved_entry(tmp_path)
    broker = SimulatedExecutionBroker(name="SIM")
    submitted = tm.deploy_execution_request(request.request_id, broker)
    broker.set_order_truth(
        submitted.broker_order_id, status=BrokerOrderStatus.PARTIALLY_FILLED,
        filled_quantity=35, average_fill_price="149.25"
    )
    partial = tm.reconcile_execution_request(request.request_id, broker)
    assert partial.status == ExecutionRequestStatus.PARTIALLY_FILLED
    tm.stop()

    tm2 = CoreTMManager(SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))); tm2.start()
    restored = tm2.execution_snapshot()[0]
    assert restored.filled_quantity == 35
    broker.set_order_truth(
        submitted.broker_order_id, status=BrokerOrderStatus.FILLED,
        filled_quantity=100, average_fill_price="149.75"
    )
    filled = tm2.reconcile_execution_request(request.request_id, broker)
    assert filled.status == ExecutionRequestStatus.FILLED
    assert filled.filled_quantity == 100


def test_rejected_order_is_terminal_and_replay_does_not_resubmit(tmp_path):
    tm, request, _ = _approved_entry(tmp_path)
    broker = SimulatedExecutionBroker(name="SIM", auto_status=BrokerOrderStatus.REJECTED)
    rejected = tm.deploy_execution_request(request.request_id, broker)
    assert rejected.status == ExecutionRequestStatus.REJECTED
    again = tm.deploy_execution_request(request.request_id, broker)
    assert again.status == ExecutionRequestStatus.REJECTED
    assert broker.submit_count == 1


def test_stale_market_context_blocks_new_risk_at_handoff_and_deploy(tmp_path):
    tm, request, _ = _approved_entry(tmp_path)
    tm.patch_context("market", {"status": "STALE"}, source="TEST", reason="feed lag")
    with pytest.raises(ExecutionAuthorizationError):
        tm.deploy_execution_request(request.request_id, SimulatedExecutionBroker(name="SIM"))


def test_stale_broker_order_snapshot_cannot_roll_execution_state_backward(tmp_path):
    tm, request, t = _approved_entry(tmp_path)
    broker = SimulatedExecutionBroker(name="SIM")
    submitted = tm.deploy_execution_request(request.request_id, broker)
    fresh_time = t + timedelta(minutes=20)
    broker.set_order_truth(
        submitted.broker_order_id, status=BrokerOrderStatus.PARTIALLY_FILLED,
        filled_quantity=50, average_fill_price="149", observed_at=fresh_time
    )
    partial = tm.reconcile_execution_request(request.request_id, broker)
    assert partial.filled_quantity == 50
    broker.set_order_truth(
        submitted.broker_order_id, status=BrokerOrderStatus.ACKNOWLEDGED,
        filled_quantity=0, observed_at=fresh_time - timedelta(minutes=1)
    )
    unchanged = tm.reconcile_execution_request(request.request_id, broker)
    assert unchanged.status == ExecutionRequestStatus.PARTIALLY_FILLED
    assert unchanged.filled_quantity == 50


def test_concurrent_duplicate_deploy_calls_submit_once(tmp_path):
    tm, request, _ = _approved_entry(tmp_path)
    broker = SimulatedExecutionBroker(name="SIM")
    results = []
    errors = []

    def run():
        try:
            results.append(tm.deploy_execution_request(request.request_id, broker))
        except Exception as exc:  # pragma: no cover - diagnostic capture
            errors.append(exc)

    threads = [Thread(target=run) for _ in range(8)]
    for th in threads: th.start()
    for th in threads: th.join()
    assert not errors
    assert len(results) == 8
    assert broker.submit_count == 1
    assert all(r.status == ExecutionRequestStatus.SUBMITTED for r in results)


def _run_replay(workdir):
    tm, request, _ = _approved_entry(workdir)
    broker = SimulatedExecutionBroker(name="SIM")
    submitted = tm.deploy_execution_request(request.request_id, broker)
    broker.set_order_truth(
        submitted.broker_order_id, status=BrokerOrderStatus.PARTIALLY_FILLED,
        filled_quantity=25, average_fill_price="149.2"
    )
    tm.reconcile_execution_request(request.request_id, broker)
    broker.set_order_truth(
        submitted.broker_order_id, status=BrokerOrderStatus.FILLED,
        filled_quantity=100, average_fill_price="149.6"
    )
    final = tm.reconcile_execution_request(request.request_id, broker)
    return {
        "status": final.status.value,
        "filled_quantity": final.filled_quantity,
        "average_fill_price": str(final.average_fill_price),
        "submit_count": broker.submit_count,
    }


def test_end_to_end_execution_replay_converges_to_same_business_state(tmp_path):
    a = tmp_path / "a"; b = tmp_path / "b"; a.mkdir(); b.mkdir()
    assert _run_replay(a) == _run_replay(b) == {
        "status": "FILLED", "filled_quantity": 100,
        "average_fill_price": "149.6", "submit_count": 1,
    }

def test_stale_market_context_blocks_creation_of_new_execution_handoff(tmp_path):
    # Build only through Risk PASS, then stale the market before request creation.
    repo = SQLiteRuntimeRepository(Database(tmp_path / "pre_stale.db"))
    tm = CoreTMManager(repo); tm.start()
    t = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)
    tm.reconcile_broker_truth(MockBroker(BrokerAccountSnapshot.create(broker="SIM", observed_at=t), name="SIM"))
    intake = tm.ingest_trade_observation(
        src_id="Y", source="TEST", observed_at=t,
        intent=NormalizedTradeIntent(
            underlying="PNB", direction="BULLISH", setup="BREAKOUT", trade_type="DAY",
            instrument_type="OPTION", option_type="CE", contract_symbol="PNB26SEP117CE",
            expiry="2026-09-29", strike="117", premium="5"
        )
    )
    intent = tm.create_entry_intent(
        episode=intake.episode, underlying="PNB", direction="BULLISH", trade_type=TradeType.DAY,
        asset_class=AssetClass.EQUITY, instrument_type=InstrumentType.OPTION,
        horizon_at=t+timedelta(hours=5), expiry_date="2026-09-29",
        contract_symbol="PNB26SEP117CE", option_type="CE", strike="117",
        trigger=PriceCondition(ConditionOperator.ABOVE,"117"),
        confirmation=PriceCondition(ConditionOperator.ABOVE,"117"),
        invalidation=PriceCondition(ConditionOperator.BELOW,"116"),
        premium_min="4", premium_max="6", created_at=t, updated_at=t
    )
    tm.evaluate_entry_intent(intent.entry_intent_id, EntryMarketSnapshot(
        observed_at=t+timedelta(minutes=15), spot="118", premium="5",
        completed_candle_close="117.5"
    ))
    intent = tm.request_entry_agent_review(intent.entry_intent_id, _ApproveGateway(), requested_at=t+timedelta(minutes=16))
    decision = tm.evaluate_entry_risk(intent.entry_intent_id, EntryRiskProposal(
        entry_intent_id=intent.entry_intent_id, requested_at=t+timedelta(minutes=17),
        planned_qty=100, planned_entry_price="5", planned_max_loss="1000"
    ))
    tm.patch_context("market", {"status": "STALE"}, source="TEST", reason="feed stopped")
    with pytest.raises(ExecutionAuthorizationError):
        tm.prepare_entry_execution_request(
            entry_intent_id=intent.entry_intent_id, risk_decision_id=decision.decision_id,
            broker="SIM", exchange="NFO", product="NRML", side=OrderSide.BUY,
            order_type=OrderType.LIMIT, created_at=t+timedelta(minutes=18)
        )

def test_concurrent_full_exit_triggers_coalesce_before_execution(tmp_path):
    from datetime import date
    from trademonitor.domain.enums import ExitAction, ExitProposalClass
    from trademonitor.domain.models import BrokerPositionSnapshot, PositionAdoptionRequest

    repo = SQLiteRuntimeRepository(Database(tmp_path / "exit_concurrent.db"))
    tm = CoreTMManager(repo); tm.start()
    t = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)
    tm.reconcile_broker_truth(MockBroker(BrokerAccountSnapshot.create(
        broker="SIM", observed_at=t,
        positions=[BrokerPositionSnapshot(
            broker="SIM", broker_position_key="NFO:EXIT-CONCURRENT", exchange="NFO",
            symbol="PNB26SEP117CE", product="NRML", quantity=100,
            average_price="5", last_price="6", observed_at=t,
        )],
    ), name="SIM"))
    pos = tm.positions_snapshot(open_only=True)[0]
    tm.adopt_position(PositionAdoptionRequest(
        position_id=pos.position_id, asset_class=AssetClass.EQUITY,
        instrument_type=InstrumentType.OPTION, trade_type=TradeType.POS,
        horizon_at=t + timedelta(days=5), expiry_date=date(2026, 9, 29),
        requested_at=t + timedelta(minutes=1), requested_by="USER", reason="manage",
    ))

    results = []
    def trigger(source):
        results.append(tm.propose_position_exit(
            pos.position_id, proposal_class=ExitProposalClass.DETERMINISTIC,
            action=ExitAction.EXIT_ALL, at=t + timedelta(minutes=2),
            created_by=source, reason=f"{source} exit trigger",
        ))

    threads = [Thread(target=trigger, args=(f"RULE-{i}",)) for i in range(6)]
    for th in threads: th.start()
    for th in threads: th.join()

    active = tm.exit_proposals_snapshot(position_id=pos.position_id, active_only=True)
    assert len(active) == 1
    assert len({r.proposal_id for r in results}) == 1
