from datetime import UTC, datetime, timedelta

import pytest

from trademonitor.brokers.execution_mock import MockExecutionBroker
from trademonitor.domain.enums import (
    BrokerOrderStatus,
    EntryIntentState,
    ExecutionRequestStatus,
    OrderSide,
    OrderType,
)
from trademonitor.execution.requests import ExecutionAuthorizationError
from trademonitor.brokers.mock import MockBroker
from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.enums import AgentVerdict, AssetClass, ConditionOperator, InstrumentType, TradeType
from trademonitor.domain.models import (AgentEntryReviewResult, BrokerAccountSnapshot, EntryMarketSnapshot, EntryRiskProposal, NormalizedTradeIntent, PriceCondition)
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository

class _ApproveGateway:
    def review_entry(self, packet):
        return AgentEntryReviewResult(review_id=packet.review_id, verdict=AgentVerdict.APPROVE, reason="ok", confidence=90, responded_at=packet.requested_at + timedelta(seconds=1))

def manager_ready_for_risk(tmp_path):
    repo = SQLiteRuntimeRepository(Database(tmp_path / "tm.db")); tm = CoreTMManager(repo); tm.start()
    t = datetime(2026,9,4,10,0,tzinfo=UTC)
    tm.reconcile_broker_truth(MockBroker(BrokerAccountSnapshot.create(broker="MOCK", observed_at=t)))
    intake = tm.ingest_trade_observation(src_id="X", source="TEST", observed_at=t, intent=NormalizedTradeIntent(underlying="KAYNES", direction="BULLISH", setup="BREAKOUT", trade_type="DAY", instrument_type="OPTION", option_type="CE", contract_symbol="KAYNES26SEP4200CE", expiry="2026-09-29", strike="4200", premium="145"))
    intent = tm.create_entry_intent(episode=intake.episode, underlying="KAYNES", direction="BULLISH", trade_type=TradeType.DAY, asset_class=AssetClass.EQUITY, instrument_type=InstrumentType.OPTION, horizon_at=t+timedelta(hours=5), expiry_date="2026-09-29", contract_symbol="KAYNES26SEP4200CE", option_type="CE", strike="4200", trigger=PriceCondition(ConditionOperator.ABOVE,"4100"), confirmation=PriceCondition(ConditionOperator.ABOVE,"4100"), invalidation=PriceCondition(ConditionOperator.BELOW,"4050"), premium_min="130", premium_max="160", created_at=t, updated_at=t)
    intent = tm.evaluate_entry_intent(intent.entry_intent_id, EntryMarketSnapshot(observed_at=t+timedelta(minutes=15), spot="4120", premium="150", completed_candle_close="4115"))
    intent = tm.request_entry_agent_review(intent.entry_intent_id, _ApproveGateway(), requested_at=t+timedelta(minutes=16))
    return tm, repo, intent, t

def proposal(intent, t):
    return EntryRiskProposal(entry_intent_id=intent.entry_intent_id, requested_at=t+timedelta(minutes=17), planned_qty=100, planned_entry_price="150", planned_max_loss="3000")


def _risk_approved(tmp_path):
    tm, _, intent, t = manager_ready_for_risk(tmp_path)
    decision = tm.evaluate_entry_risk(intent.entry_intent_id, proposal(intent, t))
    assert tm.entry_snapshot()[0].state == EntryIntentState.RISK_APPROVED
    return tm, intent, decision, t


def _prepare(tm, intent, decision, t):
    return tm.prepare_entry_execution_request(
        entry_intent_id=intent.entry_intent_id,
        risk_decision_id=decision.decision_id,
        broker="MOCK",
        exchange="NFO",
        product="NRML",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        created_at=t + timedelta(minutes=18),
    )


def test_entry_execution_request_requires_current_risk_permission(tmp_path):
    tm, intent, decision, t = _risk_approved(tmp_path)
    req = _prepare(tm, intent, decision, t)
    assert req.status == ExecutionRequestStatus.READY
    assert req.quantity == decision.proposal.planned_qty
    assert req.limit_price == decision.proposal.planned_entry_price
    assert req.risk_decision_id == decision.decision_id


def test_profile_change_invalidates_old_risk_permission(tmp_path):
    tm, intent, decision, t = _risk_approved(tmp_path)
    change = tm.admin_propose_risk_profile_change(reason="new controls", max_position_value="999999")
    tm.admin_confirm_risk_profile_change(change.change_id, confirmation="CONFIRM")
    with pytest.raises(ExecutionAuthorizationError):
        _prepare(tm, intent, decision, t)


def test_broker_truth_change_after_risk_pass_requires_re_risk(tmp_path):
    tm, intent, decision, t = _risk_approved(tmp_path)
    from trademonitor.brokers.mock import MockBroker
    from trademonitor.domain.models import BrokerAccountSnapshot
    tm.reconcile_broker_truth(MockBroker(BrokerAccountSnapshot.create(
        broker="MOCK", observed_at=t + timedelta(minutes=18)
    )))
    with pytest.raises(ExecutionAuthorizationError):
        _prepare(tm, intent, decision, t)


def test_duplicate_handoff_returns_same_execution_request(tmp_path):
    tm, intent, decision, t = _risk_approved(tmp_path)
    a = _prepare(tm, intent, decision, t)
    b = _prepare(tm, intent, decision, t)
    assert a.request_id == b.request_id
    assert a.idempotency_key == b.idempotency_key


def test_module_m_duplicate_deploy_submits_once(tmp_path):
    tm, intent, decision, t = _risk_approved(tmp_path)
    req = _prepare(tm, intent, decision, t)
    broker = MockExecutionBroker(name="MOCK")
    first = tm.deploy_execution_request(req.request_id, broker)
    second = tm.deploy_execution_request(req.request_id, broker)
    assert first.status == ExecutionRequestStatus.SUBMITTED
    assert second.request_id == first.request_id
    assert broker.submit_count == 1


def test_partial_fill_and_fill_follow_broker_truth(tmp_path):
    tm, intent, decision, t = _risk_approved(tmp_path)
    req = _prepare(tm, intent, decision, t)
    broker = MockExecutionBroker(name="MOCK")
    submitted = tm.deploy_execution_request(req.request_id, broker)
    broker.set_order_truth(
        submitted.broker_order_id,
        status=BrokerOrderStatus.PARTIALLY_FILLED,
        filled_quantity=40,
        average_fill_price="149",
    )
    partial = tm.reconcile_execution_request(req.request_id, broker)
    assert partial.status == ExecutionRequestStatus.PARTIALLY_FILLED
    assert partial.filled_quantity == 40
    broker.set_order_truth(
        submitted.broker_order_id,
        status=BrokerOrderStatus.FILLED,
        filled_quantity=req.quantity,
        average_fill_price="149.5",
    )
    filled = tm.reconcile_execution_request(req.request_id, broker)
    assert filled.status == ExecutionRequestStatus.FILLED
    assert filled.filled_quantity == req.quantity


def test_rejection_and_cancel_are_broker_truth(tmp_path):
    tm, intent, decision, t = _risk_approved(tmp_path)
    req = _prepare(tm, intent, decision, t)
    broker = MockExecutionBroker(name="MOCK", auto_status=BrokerOrderStatus.REJECTED)
    rejected = tm.deploy_execution_request(req.request_id, broker)
    assert rejected.status == ExecutionRequestStatus.REJECTED

    # Separate request needed for cancellation path.
    # A second trade/risk cycle is intentionally not manufactured here; direct
    # engine behavior is covered via the first request in another database.


def test_execution_context_is_versioned_and_paper_only(tmp_path):
    tm, intent, decision, t = _risk_approved(tmp_path)
    before = tm.status_snapshot()["execution"]
    _prepare(tm, intent, decision, t)
    after = tm.status_snapshot()["execution"]
    assert after["version"] > before["version"]
    assert after["data"]["real_broker_writes_enabled"] is False


def test_exit_uses_same_module_m_handoff(tmp_path):
    from datetime import date
    from trademonitor.domain.enums import AssetClass, ExitAction, ExitProposalClass, InstrumentType, TradeType
    from trademonitor.domain.models import BrokerPositionSnapshot, PositionAdoptionRequest

    repo = SQLiteRuntimeRepository(Database(tmp_path / "exit.db")); tm = CoreTMManager(repo); tm.start()
    t = datetime(2026,9,4,10,0,tzinfo=UTC)
    tm.reconcile_broker_truth(MockBroker(BrokerAccountSnapshot.create(
        broker="MOCK", observed_at=t,
        positions=[BrokerPositionSnapshot(
            broker="MOCK", broker_position_key="NFO:EXIT", exchange="NFO",
            symbol="PNB26SEP117CE", product="NRML", quantity=100,
            average_price="5", last_price="6", observed_at=t,
        )],
    )))
    pos = tm.positions_snapshot(open_only=True)[0]
    tm.adopt_position(PositionAdoptionRequest(
        position_id=pos.position_id, asset_class=AssetClass.EQUITY,
        instrument_type=InstrumentType.OPTION, trade_type=TradeType.POS,
        horizon_at=t+timedelta(days=5), expiry_date=date(2026,9,29),
        requested_at=t+timedelta(minutes=1), requested_by="USER", reason="manage",
    ))
    ep = tm.propose_position_exit(
        pos.position_id, proposal_class=ExitProposalClass.DETERMINISTIC,
        action=ExitAction.EXIT_ALL, at=t+timedelta(minutes=2),
        created_by="POLICY", reason="target reached",
    )
    req = tm.prepare_exit_execution_request(
        exit_proposal_id=ep.proposal_id, broker="MOCK", order_type=OrderType.MARKET,
        created_at=t+timedelta(minutes=3),
    )
    assert req.quantity == 100
    assert req.side == OrderSide.SELL
    broker = MockExecutionBroker(name="MOCK")
    deployed = tm.deploy_execution_request(req.request_id, broker)
    assert deployed.status == ExecutionRequestStatus.SUBMITTED
    assert broker.submit_count == 1


def test_submission_exception_becomes_uncertain_and_never_blind_retries(tmp_path):
    tm, intent, decision, t = _risk_approved(tmp_path)
    req = _prepare(tm, intent, decision, t)

    class UncertainBroker(MockExecutionBroker):
        def submit_order(self, order):
            self.submit_count += 1
            raise TimeoutError("ack lost")

    broker = UncertainBroker(name="MOCK")
    first = tm.deploy_execution_request(req.request_id, broker)
    assert first.status == ExecutionRequestStatus.UNCERTAIN
    second = tm.deploy_execution_request(req.request_id, broker)
    assert second.status == ExecutionRequestStatus.UNCERTAIN
    assert broker.submit_count == 1


def test_tgt1_rejects_non_simulation_broker_write(tmp_path):
    tm, intent, decision, t = _risk_approved(tmp_path)
    req = _prepare(tm, intent, decision, t)

    class PretendLiveBroker(MockExecutionBroker):
        @property
        def is_simulation(self):
            return False

    with pytest.raises(PermissionError):
        tm.deploy_execution_request(req.request_id, PretendLiveBroker(name="MOCK"))


def test_explicit_cancel_reconciles_to_broker_cancelled_truth(tmp_path):
    work = tmp_path / "cancel"
    work.mkdir()
    tm, intent, decision, t = _risk_approved(work)
    req = _prepare(tm, intent, decision, t)
    broker = MockExecutionBroker(name="MOCK")
    submitted = tm.deploy_execution_request(req.request_id, broker)
    assert submitted.status == ExecutionRequestStatus.SUBMITTED
    cancelled = tm.cancel_execution_request(req.request_id, broker)
    assert cancelled.status == ExecutionRequestStatus.CANCELLED


def test_entry_request_is_rechecked_immediately_before_module_m(tmp_path):
    tm, intent, decision, t = _risk_approved(tmp_path)
    req = _prepare(tm, intent, decision, t)
    change = tm.admin_propose_risk_profile_change(reason="tighten after handoff", max_position_value="999999")
    tm.admin_confirm_risk_profile_change(change.change_id, confirmation="CONFIRM")
    with pytest.raises(ExecutionAuthorizationError):
        tm.deploy_execution_request(req.request_id, MockExecutionBroker(name="MOCK"))


def test_exit_request_requires_current_broker_truth_at_handoff(tmp_path):
    from datetime import date
    from trademonitor.domain.enums import AssetClass, ExitAction, ExitProposalClass, InstrumentType, TradeType
    from trademonitor.domain.models import BrokerPositionSnapshot, PositionAdoptionRequest

    repo = SQLiteRuntimeRepository(Database(tmp_path / "exit_stale.db")); tm = CoreTMManager(repo); tm.start()
    t = datetime(2026,9,4,10,0,tzinfo=UTC)
    tm.reconcile_broker_truth(MockBroker(BrokerAccountSnapshot.create(
        broker="MOCK", observed_at=t,
        positions=[BrokerPositionSnapshot(
            broker="MOCK", broker_position_key="NFO:EXIT2", exchange="NFO",
            symbol="PNB26SEP117CE", product="NRML", quantity=100,
            average_price="5", last_price="6", observed_at=t,
        )],
    )))
    pos = tm.positions_snapshot(open_only=True)[0]
    tm.adopt_position(PositionAdoptionRequest(
        position_id=pos.position_id, asset_class=AssetClass.EQUITY,
        instrument_type=InstrumentType.OPTION, trade_type=TradeType.POS,
        horizon_at=t+timedelta(days=5), expiry_date=date(2026,9,29),
        requested_at=t+timedelta(minutes=1), requested_by="USER", reason="manage",
    ))
    ep = tm.propose_position_exit(
        pos.position_id, proposal_class=ExitProposalClass.DETERMINISTIC,
        action=ExitAction.EXIT_ALL, at=t+timedelta(minutes=2),
        created_by="POLICY", reason="target reached",
    )
    # Simulate restart semantics: last-known position exists but current-runtime broker truth is not confirmed.
    tm.contexts.get("broker").patch({"runtime_reconciled": False})
    with pytest.raises(ExecutionAuthorizationError):
        tm.prepare_exit_execution_request(
            exit_proposal_id=ep.proposal_id, broker="MOCK", order_type=OrderType.MARKET,
            created_at=t+timedelta(minutes=3),
        )
