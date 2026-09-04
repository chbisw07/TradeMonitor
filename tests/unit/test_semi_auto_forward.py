from datetime import timedelta

import pytest

from trademonitor.brokers.execution_mock import MockExecutionBroker
from trademonitor.domain.enums import ExecutionApprovalStatus, ExecutionMode
from trademonitor.domain.models import utc_now
from trademonitor.execution.approval import SemiAutoApprovalError
from trademonitor.core.manager import CoreTMManager
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository

from trademonitor.brokers.mock import MockBroker
from trademonitor.domain.enums import (
    AgentVerdict, AssetClass, ConditionOperator, EntryIntentState,
    InstrumentType, OrderSide, OrderType, TradeType,
)
from trademonitor.domain.models import (
    AgentEntryReviewResult, BrokerAccountSnapshot, EntryMarketSnapshot,
    EntryRiskProposal, NormalizedTradeIntent, PriceCondition,
)


class _ApproveGateway:
    def review_entry(self, packet):
        return AgentEntryReviewResult(
            review_id=packet.review_id, verdict=AgentVerdict.APPROVE,
            reason="ok", confidence=90, responded_at=packet.requested_at + timedelta(seconds=1),
        )


def _risk_approved(tmp_path):
    repo = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    tm = CoreTMManager(repo); tm.start()
    from datetime import UTC, datetime
    t = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)
    tm.reconcile_broker_truth(MockBroker(BrokerAccountSnapshot.create(broker="MOCK", observed_at=t)))
    intake = tm.ingest_trade_observation(
        src_id="X", source="TEST", observed_at=t,
        intent=NormalizedTradeIntent(
            underlying="KAYNES", direction="BULLISH", setup="BREAKOUT", trade_type="DAY",
            instrument_type="OPTION", option_type="CE", contract_symbol="KAYNES26SEP4200CE",
            expiry="2026-09-29", strike="4200", premium="145"),
    )
    intent = tm.create_entry_intent(
        episode=intake.episode, underlying="KAYNES", direction="BULLISH", trade_type=TradeType.DAY,
        asset_class=AssetClass.EQUITY, instrument_type=InstrumentType.OPTION,
        horizon_at=t+timedelta(hours=5), expiry_date="2026-09-29",
        contract_symbol="KAYNES26SEP4200CE", option_type="CE", strike="4200",
        trigger=PriceCondition(ConditionOperator.ABOVE,"4100"),
        confirmation=PriceCondition(ConditionOperator.ABOVE,"4100"),
        invalidation=PriceCondition(ConditionOperator.BELOW,"4050"),
        premium_min="130", premium_max="160", created_at=t, updated_at=t,
    )
    intent = tm.evaluate_entry_intent(intent.entry_intent_id, EntryMarketSnapshot(
        observed_at=t+timedelta(minutes=15), spot="4120", premium="150", completed_candle_close="4115"))
    intent = tm.request_entry_agent_review(intent.entry_intent_id, _ApproveGateway(), requested_at=t+timedelta(minutes=16))
    decision = tm.evaluate_entry_risk(intent.entry_intent_id, EntryRiskProposal(
        entry_intent_id=intent.entry_intent_id, requested_at=t+timedelta(minutes=17),
        planned_qty=100, planned_entry_price="150", planned_max_loss="3000"))
    assert tm.entry_snapshot()[0].state == EntryIntentState.RISK_APPROVED
    return tm, intent, decision, t


def _prepare(tm, intent, decision, t):
    return tm.prepare_entry_execution_request(
        entry_intent_id=intent.entry_intent_id, risk_decision_id=decision.decision_id,
        broker="MOCK", exchange="NFO", product="NRML", side=OrderSide.BUY,
        order_type=OrderType.LIMIT, created_at=t + timedelta(minutes=18),
    )


class PretendLiveBroker(MockExecutionBroker):
    @property
    def is_simulation(self):
        return False


def _semi_auto_manager(tmp_path):
    # Recreate the existing risk-approved fixture using a SEMI_AUTO manager.
    # The existing helper creates a PAPER manager, so we re-open its durable DB
    # with the same state under the TGT3 execution control plane.
    tm0, intent, decision, t = _risk_approved(tmp_path)
    req = _prepare(tm0, intent, decision, t)
    tm0.stop()
    repo = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    tm = CoreTMManager(
        repo,
        execution_mode=ExecutionMode.SEMI_AUTO,
        allow_real_broker_writes=True,
        semi_auto_approval_ttl_seconds=60,
    )
    tm.start()
    # Fresh current-runtime broker reconciliation is required after restart.
    from trademonitor.brokers.mock import MockBroker
    from trademonitor.domain.models import BrokerAccountSnapshot
    tm.reconcile_broker_truth(MockBroker(BrokerAccountSnapshot.create(
        broker="MOCK", observed_at=t
    )))
    return tm, req


def test_paper_mode_still_rejects_real_broker(tmp_path):
    tm, intent, decision, t = _risk_approved(tmp_path)
    req = _prepare(tm, intent, decision, t)
    with pytest.raises(PermissionError):
        tm.deploy_execution_request(req.request_id, PretendLiveBroker(name="MOCK"))


def test_semi_auto_real_deploy_requires_explicit_user_approval(tmp_path):
    tm, req = _semi_auto_manager(tmp_path)
    with pytest.raises(SemiAutoApprovalError):
        tm.deploy_execution_request(req.request_id, PretendLiveBroker(name="MOCK"))

    pending = tm.request_semi_auto_execution_approval(
        req.request_id, requested_by="SYSTEM", reason="controlled forward test"
    )
    assert pending.status == ExecutionApprovalStatus.PENDING
    approved = tm.resolve_semi_auto_execution_approval(
        req.request_id,
        approve=True,
        decided_by="USER",
        reason="small controlled test",
        confirmation="APPROVE",
    )
    assert approved.status == ExecutionApprovalStatus.APPROVED

    broker = PretendLiveBroker(name="MOCK")
    deployed = tm.deploy_execution_request(req.request_id, broker)
    assert deployed.broker_order_id
    assert broker.submit_count == 1


def test_reject_does_not_grant_execution(tmp_path):
    tm, req = _semi_auto_manager(tmp_path)
    tm.request_semi_auto_execution_approval(req.request_id, reason="review")
    rejected = tm.resolve_semi_auto_execution_approval(
        req.request_id,
        approve=False,
        decided_by="USER",
        reason="skip",
        confirmation="REJECT",
    )
    assert rejected.status == ExecutionApprovalStatus.REJECTED
    with pytest.raises(SemiAutoApprovalError):
        tm.deploy_execution_request(req.request_id, PretendLiveBroker(name="MOCK"))


def test_wrong_confirmation_phrase_is_rejected(tmp_path):
    tm, req = _semi_auto_manager(tmp_path)
    tm.request_semi_auto_execution_approval(req.request_id, reason="review")
    with pytest.raises(SemiAutoApprovalError):
        tm.resolve_semi_auto_execution_approval(
            req.request_id,
            approve=True,
            decided_by="USER",
            reason="test",
            confirmation="YES",
        )


def test_approval_ttl_is_enforced(tmp_path):
    tm0, intent, decision, t = _risk_approved(tmp_path)
    req = _prepare(tm0, intent, decision, t)
    tm0.stop()
    repo = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    tm = CoreTMManager(repo, execution_mode=ExecutionMode.SEMI_AUTO,
                       allow_real_broker_writes=True,
                       semi_auto_approval_ttl_seconds=1)
    tm.start()
    from trademonitor.brokers.mock import MockBroker
    from trademonitor.domain.models import BrokerAccountSnapshot
    tm.reconcile_broker_truth(MockBroker(BrokerAccountSnapshot.create(broker="MOCK", observed_at=t)))
    at = utc_now() - timedelta(seconds=5)
    tm.request_semi_auto_execution_approval(req.request_id, reason="review", at=at)
    tm.resolve_semi_auto_execution_approval(
        req.request_id, approve=True, decided_by="USER", reason="test",
        confirmation="APPROVE", at=at,
    )
    with pytest.raises(SemiAutoApprovalError, match="expired"):
        tm.deploy_execution_request(req.request_id, PretendLiveBroker(name="MOCK"))


def test_auto_mode_is_not_available_in_tgt3(tmp_path):
    repo = SQLiteRuntimeRepository(Database(tmp_path / "auto.db"))
    with pytest.raises(ValueError, match="AUTO"):
        CoreTMManager(repo, execution_mode=ExecutionMode.AUTO)


def test_fresh_same_broker_truth_does_not_invalidate_risk_pass(tmp_path):
    tm, intent, decision, t = _risk_approved(tmp_path)
    # Same account facts, later observation time: this is a fresh confirmation, not a material Risk change.
    tm.reconcile_broker_truth(MockBroker(BrokerAccountSnapshot.create(
        broker="MOCK", observed_at=t + timedelta(minutes=30)
    )))
    req = _prepare(tm, intent, decision, t)
    assert req.risk_decision_id == decision.decision_id


def test_approved_semi_auto_decision_survives_restart_but_still_rechecks_broker_and_risk(tmp_path):
    tm, req = _semi_auto_manager(tmp_path)
    tm.request_semi_auto_execution_approval(req.request_id, reason="forward test")
    tm.resolve_semi_auto_execution_approval(
        req.request_id, approve=True, decided_by="USER", reason="approved", confirmation="APPROVE"
    )
    tm.stop()

    repo = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    restarted = CoreTMManager(
        repo, execution_mode=ExecutionMode.SEMI_AUTO, allow_real_broker_writes=True,
        semi_auto_approval_ttl_seconds=60,
    )
    restarted.start()
    # Startup deliberately clears runtime broker confirmation; real deployment cannot proceed yet.
    with pytest.raises(Exception):
        restarted.deploy_execution_request(req.request_id, PretendLiveBroker(name="MOCK"))
    from datetime import UTC, datetime
    restarted.reconcile_broker_truth(MockBroker(BrokerAccountSnapshot.create(
        broker="MOCK", observed_at=datetime(2026, 9, 4, 10, 1, tzinfo=UTC)
    )))
    deployed = restarted.deploy_execution_request(req.request_id, PretendLiveBroker(name="MOCK"))
    assert deployed.broker_order_id
