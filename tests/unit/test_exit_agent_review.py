"""TM3/TGT4 strategic-exit Agents validation and escalation tests."""

from datetime import UTC, date, datetime, timedelta

import pytest

from trademonitor.brokers.mock import MockBroker
from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.enums import (
    AgentVerdict,
    AssetClass,
    ExitAction,
    ExitProposalClass,
    ExitProposalStatus,
    InstrumentType,
    TradeType,
)
from trademonitor.domain.models import (
    AgentExitReviewResult,
    BrokerAccountSnapshot,
    BrokerPositionSnapshot,
    PositionAdoptionRequest,
)
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository
from trademonitor.positions.review import ExitReviewError


class FixedExitGateway:
    def __init__(self, verdict, *, reason="reviewed", confidence=82, suggestion=None):
        self.verdict = AgentVerdict(verdict)
        self.reason = reason
        self.confidence = confidence
        self.suggestion = suggestion
        self.calls = []

    def review_exit(self, packet):
        self.calls.append(packet)
        return AgentExitReviewResult(
            review_id=packet.review_id,
            verdict=self.verdict,
            reason=self.reason,
            confidence=self.confidence,
            suggestion=self.suggestion,
            responded_at=packet.requested_at + timedelta(seconds=1),
        )


class FailingExitGateway:
    def review_exit(self, packet):
        raise TimeoutError("agents timed out")


def _ready_core(tmp_path):
    repo = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    tm = CoreTMManager(repo); tm.start()
    at = datetime(2026, 9, 4, 5, 0, tzinfo=UTC)
    snap = BrokerAccountSnapshot.create(
        broker="MOCK", observed_at=at,
        positions=[BrokerPositionSnapshot(
            broker="MOCK", broker_position_key="NFO:X", exchange="NFO",
            symbol="X26SEP100CE", product="NRML", quantity=100,
            average_price="100", last_price="125", unrealized_pnl="2500", observed_at=at,
        )],
    )
    pos = tm.reconcile_broker_truth(MockBroker(snapshot=snap))[0]
    tm.adopt_position(PositionAdoptionRequest(
        position_id=pos.position_id, asset_class=AssetClass.EQUITY,
        instrument_type=InstrumentType.OPTION, trade_type=TradeType.POS,
        horizon_at=at+timedelta(days=7), expiry_date=date(2026, 9, 29),
        requested_at=at+timedelta(minutes=1), requested_by="USER", reason="manage",
    ))
    proposal = tm.propose_position_exit(
        pos.position_id, proposal_class=ExitProposalClass.STRATEGIC,
        action=ExitAction.EXIT_ALL, at=at+timedelta(minutes=2),
        created_by="EXIT_MONITOR", reason="momentum deterioration near resistance",
    )
    assert proposal.status == ExitProposalStatus.PENDING
    return tm, pos, proposal, at


def test_agent_approve_marks_strategic_exit_approved_without_user_escalation(tmp_path):
    tm, _, proposal, at = _ready_core(tmp_path)
    gateway = FixedExitGateway(AgentVerdict.APPROVE, suggestion="Trail tightly if held")
    updated = tm.request_exit_agent_review(
        proposal.proposal_id, gateway, requested_at=at+timedelta(minutes=3)
    )
    assert updated.status == ExitProposalStatus.APPROVED
    assert len(gateway.calls) == 1
    assert tm.attention_snapshot() == []
    review = tm.exit_review_snapshot(exit_proposal_id=proposal.proposal_id)[0]
    assert review.result.verdict == AgentVerdict.APPROVE
    assert review.result.suggestion == "Trail tightly if held"


@pytest.mark.parametrize("verdict", [AgentVerdict.REJECT, AgentVerdict.RETREAT_WAIT])
def test_agent_disagreement_escalates_to_user(tmp_path, verdict):
    tm, _, proposal, at = _ready_core(tmp_path)
    updated = tm.request_exit_agent_review(
        proposal.proposal_id,
        FixedExitGateway(verdict, reason="independent objection", suggestion="Wait for next 15m close"),
        requested_at=at+timedelta(minutes=3),
    )
    assert updated.status == ExitProposalStatus.PENDING
    attention = tm.attention_snapshot()
    assert len(attention) == 1
    assert "APPROVE / REJECT / RETREAT_WAIT" in attention[0].detail
    assert "Wait for next 15m close" in attention[0].detail


def test_user_approve_overrides_agent_reject_at_exit_decision_layer(tmp_path):
    tm, _, proposal, at = _ready_core(tmp_path)
    tm.request_exit_agent_review(
        proposal.proposal_id, FixedExitGateway(AgentVerdict.REJECT),
        requested_at=at+timedelta(minutes=3),
    )
    resolved = tm.resolve_exit_agent_decision(
        proposal.proposal_id, AgentVerdict.APPROVE,
        at=at+timedelta(minutes=4), reason="User wants to book now",
    )
    assert resolved.status == ExitProposalStatus.APPROVED
    assert tm.attention_snapshot() == []
    review = tm.exit_review_snapshot(exit_proposal_id=proposal.proposal_id)[0]
    assert review.user_decision == AgentVerdict.APPROVE


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        (AgentVerdict.REJECT, ExitProposalStatus.REJECTED),
        (AgentVerdict.RETREAT_WAIT, ExitProposalStatus.RETREAT_WAIT),
    ],
)
def test_user_can_reject_or_retreat_after_agent_disagreement(tmp_path, decision, expected):
    tm, _, proposal, at = _ready_core(tmp_path)
    tm.request_exit_agent_review(
        proposal.proposal_id, FixedExitGateway(AgentVerdict.RETREAT_WAIT),
        requested_at=at+timedelta(minutes=3),
    )
    resolved = tm.resolve_exit_agent_decision(
        proposal.proposal_id, decision,
        at=at+timedelta(minutes=4), reason="User resolution",
    )
    assert resolved.status == expected
    assert tm.exit_proposals_snapshot(active_only=True) == []


def test_agent_unavailable_escalates_and_never_implies_exit_approval(tmp_path):
    tm, _, proposal, at = _ready_core(tmp_path)
    updated = tm.request_exit_agent_review(
        proposal.proposal_id, FailingExitGateway(), requested_at=at+timedelta(minutes=3)
    )
    assert updated.status == ExitProposalStatus.PENDING
    review = tm.exit_review_snapshot(exit_proposal_id=proposal.proposal_id)[0]
    assert review.status.value == "FAILED"
    assert review.result is None
    assert "AGENT_UNAVAILABLE" in tm.attention_snapshot()[0].detail


def test_protective_and_deterministic_exits_bypass_agent_gate(tmp_path):
    tm, pos, strategic, at = _ready_core(tmp_path)
    # A later protective full-exit trigger must promote the existing strategic path,
    # not remain blocked behind its Agent/User review.
    protective = tm.propose_position_exit(
        pos.position_id, proposal_class=ExitProposalClass.PROTECTIVE,
        action=ExitAction.EXIT_ALL, at=at+timedelta(minutes=3),
        created_by="POSITION_RULE", reason="hard stop breached",
    )
    assert protective.proposal_id == strategic.proposal_id
    assert protective.proposal_class == ExitProposalClass.PROTECTIVE
    assert protective.status == ExitProposalStatus.APPROVED
    with pytest.raises(ExitReviewError):
        tm.request_exit_agent_review(
            protective.proposal_id, FixedExitGateway(AgentVerdict.RETREAT_WAIT),
            requested_at=at+timedelta(minutes=4),
        )


def test_agent_suggestion_is_advice_only_and_does_not_create_management_rule(tmp_path):
    tm, pos, proposal, at = _ready_core(tmp_path)
    before = tm.position_management_rules_snapshot(position_id=pos.position_id)
    tm.request_exit_agent_review(
        proposal.proposal_id,
        FixedExitGateway(AgentVerdict.REJECT, suggestion="Lock 2000 profit and hold"),
        requested_at=at+timedelta(minutes=3),
    )
    after = tm.position_management_rules_snapshot(position_id=pos.position_id)
    assert before == after
