"""Integration tests for TM1/TGT2 broker truth and durable position state."""

from trademonitor.brokers.mock import MockBroker
from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.enums import ManagementStatus, PositionState
from trademonitor.domain.models import BrokerAccountSnapshot, BrokerFundsSnapshot, BrokerPositionSnapshot
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


def build_manager(path) -> CoreTMManager:
    return CoreTMManager(SQLiteRuntimeRepository(Database(path)))


def snapshot(*, qty: int = 50) -> BrokerAccountSnapshot:
    return BrokerAccountSnapshot.create(
        broker="MOCK",
        positions=[
            BrokerPositionSnapshot(
                broker="MOCK",
                broker_position_key="NFO:PNB26SEP117CE:NRML",
                exchange="NFO",
                symbol="PNB26SEP117CE",
                product="NRML",
                quantity=qty,
                average_price="4.85",
                last_price="5.20",
                unrealized_pnl="1750",
            )
        ],
        funds=BrokerFundsSnapshot.create(
            available_cash="250000", used_margin="50000", net_value="300000"
        ),
        order_count=3,
        fill_count=2,
    )


def test_core_reconciles_broker_truth_into_contexts_and_positions(tmp_path) -> None:
    repository = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    manager = CoreTMManager(repository)
    broker = MockBroker(snapshot())
    manager.start()

    positions = manager.reconcile_broker_truth(broker)

    assert len(positions) == 1
    assert positions[0].management_status == ManagementStatus.UNMANAGED
    assert positions[0].state == PositionState.OPEN

    status = manager.status_snapshot()
    assert status["broker"]["data"]["status"] == "RECONCILED"
    assert status["broker"]["data"]["read_only"] is True
    assert status["broker"]["data"]["funds"]["available_cash"] == "250000"
    assert status["position"]["data"]["unmanaged_open"] == 1
    assert status["position"]["data"]["managed_open"] == 0

    event_names = [event["name"] for event in repository.list_events()]
    assert "BROKER_POSITION_DISCOVERED" in event_names
    assert "BROKER_RECONCILED" in event_names

    manager.stop()


def test_reconciled_position_survives_restart_then_accepts_broker_closure(tmp_path) -> None:
    db_path = tmp_path / "tm.db"
    first = build_manager(db_path)
    broker = MockBroker(snapshot())
    first.start()
    first.reconcile_broker_truth(broker)
    first.stop()

    second = build_manager(db_path)
    second.start()
    restored = second.positions_snapshot(open_only=True)
    assert len(restored) == 1

    broker.set_snapshot(BrokerAccountSnapshot.create(broker="MOCK", positions=[]))
    second.reconcile_broker_truth(broker)

    all_positions = second.positions_snapshot()
    assert len(all_positions) == 1
    assert all_positions[0].state == PositionState.CLOSED
    assert all_positions[0].quantity == 0
    second.stop()
