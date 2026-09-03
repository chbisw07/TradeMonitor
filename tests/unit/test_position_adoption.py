"""TM3/TGT1 unit tests for the explicit UNMANAGED -> MANAGED adoption boundary."""

from datetime import UTC, date, datetime, timedelta

import pytest

from trademonitor.domain.enums import (
    AssetClass,
    InstrumentType,
    ManagementStatus,
    PositionOrigin,
    TradeType,
)
from trademonitor.domain.models import (
    BrokerAccountSnapshot,
    BrokerPositionSnapshot,
    PositionAdoptionRequest,
)
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository
from trademonitor.positions.manager import (
    AlreadyManagedPositionError,
    PositionAdoptionError,
    PositionManager,
    UnmanagedPositionError,
)


def _snapshot(at: datetime, qty: int = 100) -> BrokerAccountSnapshot:
    return BrokerAccountSnapshot.create(
        broker="MOCK",
        observed_at=at,
        positions=[
            BrokerPositionSnapshot(
                broker="MOCK",
                broker_position_key="NFO:KAYNES26SEP4200CE:NRML",
                exchange="NFO",
                symbol="KAYNES26SEP4200CE",
                product="NRML",
                quantity=qty,
                average_price="125.00",
                last_price="130.00",
                observed_at=at,
            )
        ],
    )


def _request(position_id: str, at: datetime) -> PositionAdoptionRequest:
    return PositionAdoptionRequest(
        position_id=position_id,
        asset_class=AssetClass.EQUITY,
        instrument_type=InstrumentType.OPTION,
        trade_type=TradeType.POS,
        horizon_at=at + timedelta(days=7),
        expiry_date=date(2026, 9, 29),
        requested_at=at,
        requested_by="USER",
        reason="Explicitly adopt for positional monitoring and management",
    )


def test_explicit_adoption_crosses_boundary_without_changing_broker_truth(tmp_path) -> None:
    repository = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    repository.initialize()
    manager = PositionManager(repository)
    at = datetime(2026, 9, 4, 5, 0, tzinfo=UTC)
    position = manager.reconcile(_snapshot(at))[0][0]

    with pytest.raises(UnmanagedPositionError):
        manager.require_managed(position)

    adopted, profile, events = manager.adopt(_request(position.position_id, at + timedelta(minutes=1)))

    assert adopted.management_status == ManagementStatus.MANAGED
    assert adopted.origin == PositionOrigin.BROKER_ADOPTED
    assert adopted.quantity == position.quantity
    assert adopted.average_price == position.average_price
    assert adopted.broker_position_key == position.broker_position_key
    manager.require_managed(adopted)
    assert profile.position_id == adopted.position_id
    assert profile.trade_type == TradeType.POS
    assert profile.instrument_type == InstrumentType.OPTION
    assert [event.name for event in events] == ["POSITION_ADOPTED"]


def test_adoption_requires_sufficient_management_information(tmp_path) -> None:
    repository = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    repository.initialize()
    manager = PositionManager(repository)
    at = datetime(2026, 9, 4, 5, 0, tzinfo=UTC)
    position = manager.reconcile(_snapshot(at))[0][0]

    bad = PositionAdoptionRequest(
        position_id=position.position_id,
        asset_class=AssetClass.EQUITY,
        instrument_type=InstrumentType.OPTION,
        trade_type=TradeType.POS,
        horizon_at=at + timedelta(days=3),
        expiry_date=None,
        requested_at=at,
        requested_by="USER",
        reason="adopt",
    )
    with pytest.raises(ValueError, match="expiry_date"):
        manager.adopt(bad)


def test_closed_or_already_managed_position_cannot_be_adopted_again(tmp_path) -> None:
    repository = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    repository.initialize()
    manager = PositionManager(repository)
    at = datetime(2026, 9, 4, 5, 0, tzinfo=UTC)
    position = manager.reconcile(_snapshot(at))[0][0]
    manager.adopt(_request(position.position_id, at + timedelta(minutes=1)))

    with pytest.raises(AlreadyManagedPositionError):
        manager.adopt(_request(position.position_id, at + timedelta(minutes=2)))

    repository2 = SQLiteRuntimeRepository(Database(tmp_path / "closed.db"))
    repository2.initialize()
    manager2 = PositionManager(repository2)
    closed = manager2.reconcile(_snapshot(at, qty=0))[0][0]
    with pytest.raises(PositionAdoptionError, match="not open"):
        manager2.adopt(_request(closed.position_id, at + timedelta(minutes=1)))
