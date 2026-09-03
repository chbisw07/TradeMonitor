"""Unit tests for TM1/TGT2 broker-truth position reconciliation."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trademonitor.domain.enums import ManagementStatus, PositionOrigin, PositionState
from trademonitor.domain.models import BrokerAccountSnapshot, BrokerPositionSnapshot, PositionRecord
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository
from trademonitor.positions.manager import PositionManager, UnmanagedPositionError


def broker_position(*, qty: int = 100, avg: str = "25.50", observed_at=None) -> BrokerPositionSnapshot:
    return BrokerPositionSnapshot(
        broker="MOCK",
        broker_position_key="NFO:KAYNES26SEP4200CE:NRML",
        exchange="NFO",
        symbol="KAYNES26SEP4200CE",
        product="NRML",
        quantity=qty,
        average_price=avg,
        last_price="27.25",
        unrealized_pnl="175.00",
        observed_at=observed_at,
    )


def test_new_broker_position_is_unmanaged_and_read_only(tmp_path) -> None:
    repository = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    repository.initialize()
    manager = PositionManager(repository)

    positions, events = manager.reconcile(
        BrokerAccountSnapshot.create(broker="MOCK", positions=[broker_position()])
    )

    assert len(positions) == 1
    position = positions[0]
    assert position.state == PositionState.OPEN
    assert position.management_status == ManagementStatus.UNMANAGED
    assert position.origin == PositionOrigin.BROKER_EXTERNAL
    assert [event.name for event in events] == ["BROKER_POSITION_DISCOVERED"]

    with pytest.raises(UnmanagedPositionError):
        manager.require_managed(position)


def test_reconciliation_preserves_managed_status_and_accepts_broker_quantity(tmp_path) -> None:
    repository = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    repository.initialize()
    observed = datetime(2026, 9, 3, 5, 0, tzinfo=UTC)
    existing = PositionRecord(
        position_id="p-1",
        broker="MOCK",
        broker_position_key="NFO:KAYNES26SEP4200CE:NRML",
        exchange="NFO",
        symbol="KAYNES26SEP4200CE",
        product="NRML",
        quantity=125,
        average_price="24.00",
        state=PositionState.OPEN,
        management_status=ManagementStatus.MANAGED,
        origin=PositionOrigin.TM_NATIVE,
        first_seen_at=observed,
        updated_at=observed,
    )
    repository.save_position(existing.to_record())

    manager = PositionManager(repository)
    positions, events = manager.reconcile(
        BrokerAccountSnapshot.create(
            broker="MOCK",
            positions=[broker_position(qty=75, avg="25.00", observed_at=observed + timedelta(minutes=1))],
            observed_at=observed + timedelta(minutes=1),
        )
    )

    position = positions[0]
    assert position.quantity == 75  # broker truth wins
    assert position.average_price == Decimal("25.00")
    assert position.management_status == ManagementStatus.MANAGED
    assert position.origin == PositionOrigin.TM_NATIVE
    assert [event.name for event in events] == ["BROKER_POSITION_CHANGED"]


def test_missing_previously_open_position_is_closed_by_broker_truth(tmp_path) -> None:
    repository = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    repository.initialize()
    manager = PositionManager(repository)
    first_time = datetime(2026, 9, 3, 5, 0, tzinfo=UTC)

    manager.reconcile(
        BrokerAccountSnapshot.create(
            broker="MOCK", positions=[broker_position(observed_at=first_time)], observed_at=first_time
        )
    )
    positions, events = manager.reconcile(
        BrokerAccountSnapshot.create(
            broker="MOCK", positions=[], observed_at=first_time + timedelta(minutes=1)
        )
    )

    assert positions[0].state == PositionState.CLOSED
    assert positions[0].quantity == 0
    assert [event.name for event in events] == ["BROKER_POSITION_CLOSED"]
