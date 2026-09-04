"""TM3/TGT3 durable exit-proposal and broker-truth convergence tests."""

from datetime import UTC, date, datetime, timedelta

from trademonitor.brokers.mock import MockBroker
from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.enums import AssetClass, ExitAction, ExitProposalClass, ExitProposalStatus, InstrumentType, TradeType
from trademonitor.domain.models import BrokerAccountSnapshot, BrokerPositionSnapshot, PositionAdoptionRequest
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


def _core(path):
    c = CoreTMManager(SQLiteRuntimeRepository(Database(path))); c.start(); return c


def test_exit_proposal_survives_restart_and_broker_closure_satisfies_it(tmp_path):
    db = tmp_path / "tm.db"
    at = datetime(2026, 9, 4, 5, 0, tzinfo=UTC)
    open_snap = BrokerAccountSnapshot.create(
        broker="MOCK", observed_at=at,
        positions=[BrokerPositionSnapshot(
            broker="MOCK", broker_position_key="NFO:X", exchange="NFO", symbol="X26SEP100CE",
            product="NRML", quantity=100, average_price="100", observed_at=at,
        )],
    )
    core = _core(db)
    pos = core.reconcile_broker_truth(MockBroker(snapshot=open_snap))[0]
    core.adopt_position(PositionAdoptionRequest(
        position_id=pos.position_id, asset_class=AssetClass.EQUITY,
        instrument_type=InstrumentType.OPTION, trade_type=TradeType.POS,
        horizon_at=at+timedelta(days=7), expiry_date=date(2026,9,29),
        requested_at=at+timedelta(minutes=1), requested_by="USER", reason="manage",
    ))
    proposal = core.propose_position_exit(
        pos.position_id, proposal_class=ExitProposalClass.STRATEGIC,
        action=ExitAction.EXIT_ALL, at=at+timedelta(minutes=2),
        created_by="USER", reason="strategic exit",
    )
    core.stop()

    restored = _core(db)
    assert restored.exit_proposals_snapshot(active_only=True)[0].proposal_id == proposal.proposal_id
    closed_snap = BrokerAccountSnapshot.create(broker="MOCK", observed_at=at+timedelta(minutes=10), positions=[])
    restored.reconcile_broker_truth(MockBroker(snapshot=closed_snap))
    final = restored.exit_proposals_snapshot(position_id=pos.position_id)[0]
    assert final.status == ExitProposalStatus.SATISFIED_BY_BROKER
    assert restored.positions_snapshot()[0].quantity == 0
