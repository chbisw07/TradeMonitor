"""TM3/TGT4 durable exit Agent disagreement / User escalation test."""

from datetime import UTC, date, datetime, timedelta

from trademonitor.brokers.mock import MockBroker
from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.enums import AgentVerdict, AssetClass, ExitAction, ExitProposalClass, ExitProposalStatus, InstrumentType, TradeType
from trademonitor.domain.models import AgentExitReviewResult, BrokerAccountSnapshot, BrokerPositionSnapshot, PositionAdoptionRequest
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


class RejectExitGateway:
    def review_exit(self, packet):
        return AgentExitReviewResult(
            review_id=packet.review_id,
            verdict=AgentVerdict.REJECT,
            reason="Trend still intact",
            confidence=86,
            suggestion="Wait for next completed candle",
            responded_at=packet.requested_at + timedelta(seconds=1),
        )


def _core(path):
    c = CoreTMManager(SQLiteRuntimeRepository(Database(path))); c.start(); return c


def test_exit_agent_disagreement_attention_and_resolution_survive_restart(tmp_path):
    db = tmp_path / "tm.db"
    at = datetime(2026, 9, 4, 5, 0, tzinfo=UTC)
    snap = BrokerAccountSnapshot.create(
        broker="MOCK", observed_at=at,
        positions=[BrokerPositionSnapshot(
            broker="MOCK", broker_position_key="NFO:X", exchange="NFO",
            symbol="X26SEP100CE", product="NRML", quantity=100,
            average_price="100", last_price="125", observed_at=at,
        )],
    )
    first = _core(db)
    pos = first.reconcile_broker_truth(MockBroker(snapshot=snap))[0]
    first.adopt_position(PositionAdoptionRequest(
        position_id=pos.position_id, asset_class=AssetClass.EQUITY,
        instrument_type=InstrumentType.OPTION, trade_type=TradeType.POS,
        horizon_at=at+timedelta(days=7), expiry_date=date(2026,9,29),
        requested_at=at+timedelta(minutes=1), requested_by="USER", reason="manage",
    ))
    proposal = first.propose_position_exit(
        pos.position_id, proposal_class=ExitProposalClass.STRATEGIC,
        action=ExitAction.EXIT_ALL, at=at+timedelta(minutes=2),
        created_by="EXIT_MONITOR", reason="strategic review",
    )
    first.request_exit_agent_review(
        proposal.proposal_id, RejectExitGateway(), requested_at=at+timedelta(minutes=3)
    )
    assert first.exit_proposals_snapshot(position_id=pos.position_id)[0].status == ExitProposalStatus.PENDING
    assert len(first.attention_snapshot()) == 1
    first.stop()

    second = _core(db)
    restored = second.exit_proposals_snapshot(position_id=pos.position_id)[0]
    assert restored.status == ExitProposalStatus.PENDING
    assert len(second.exit_review_snapshot(exit_proposal_id=proposal.proposal_id)) == 1
    assert any("User decision required" in x.title for x in second.attention_snapshot())
    resolved = second.resolve_exit_agent_decision(
        proposal.proposal_id, AgentVerdict.RETREAT_WAIT,
        at=at+timedelta(minutes=30), reason="Wait after restart",
    )
    assert resolved.status == ExitProposalStatus.RETREAT_WAIT
    assert second.attention_snapshot() == []
