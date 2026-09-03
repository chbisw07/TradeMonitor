"""TM3/TGT1 integration: adoption survives restart and later broker reconciliation."""

from datetime import UTC, date, datetime, timedelta

import pytest

from trademonitor.brokers.mock import MockBroker
from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.enums import AssetClass, InstrumentType, ManagementStatus, PositionOrigin, TradeType
from trademonitor.domain.models import BrokerAccountSnapshot, BrokerPositionSnapshot, PositionAdoptionRequest
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository
from trademonitor.positions.manager import PositionAdoptionError


def _manager(path) -> CoreTMManager:
    return CoreTMManager(SQLiteRuntimeRepository(Database(path)))


def _snapshot(at: datetime, *, qty: int = 75, price: str = "25.00") -> BrokerAccountSnapshot:
    return BrokerAccountSnapshot.create(
        broker="MOCK",
        observed_at=at,
        positions=[BrokerPositionSnapshot(
            broker="MOCK",
            broker_position_key="NFO:PNB26SEP117CE:NRML",
            exchange="NFO",
            symbol="PNB26SEP117CE",
            product="NRML",
            quantity=qty,
            average_price=price,
            last_price="5.20",
            observed_at=at,
        )],
    )


def _request(position_id: str, at: datetime) -> PositionAdoptionRequest:
    return PositionAdoptionRequest(
        position_id=position_id,
        asset_class=AssetClass.EQUITY,
        instrument_type=InstrumentType.OPTION,
        trade_type=TradeType.BTST,
        horizon_at=at + timedelta(days=1),
        expiry_date=date(2026, 9, 29),
        requested_at=at,
        requested_by="USER",
        reason="Adopt broker trade into TM management",
    )


def test_core_requires_current_broker_truth_before_adoption(tmp_path) -> None:
    db = tmp_path / "tm.db"
    manager = _manager(db)
    manager.start()
    # No current-runtime broker reconciliation yet.
    with pytest.raises(PositionAdoptionError, match="broker reconciliation"):
        manager.adopt_position(_request("missing", datetime(2026, 9, 4, 5, 1, tzinfo=UTC)))
    manager.stop()


def test_adoption_survives_restart_and_broker_truth_still_wins(tmp_path) -> None:
    db = tmp_path / "tm.db"
    t0 = datetime(2026, 9, 4, 5, 0, tzinfo=UTC)
    broker = MockBroker(_snapshot(t0))

    first = _manager(db)
    first.start()
    position = first.reconcile_broker_truth(broker)[0]
    adopted, profile = first.adopt_position(_request(position.position_id, t0 + timedelta(minutes=1)))
    assert adopted.management_status == ManagementStatus.MANAGED
    assert adopted.origin == PositionOrigin.BROKER_ADOPTED
    assert profile.trade_type == TradeType.BTST
    assert first.status_snapshot()["position"]["data"]["managed_open"] == 1
    first.stop()

    second = _manager(db)
    second.start()
    restored = second.positions_snapshot(open_only=True)[0]
    assert restored.management_status == ManagementStatus.MANAGED
    restored_profile = second.position_management_profile(restored.position_id)
    assert restored_profile is not None
    assert restored_profile.trade_type == TradeType.BTST

    # Broker truth changes quantity/average after restart; management status/profile survive.
    broker.set_snapshot(_snapshot(t0 + timedelta(hours=1), qty=50, price="26.00"))
    reconciled = second.reconcile_broker_truth(broker)[0]
    assert reconciled.quantity == 50
    assert str(reconciled.average_price) == "26.00"
    assert reconciled.management_status == ManagementStatus.MANAGED
    assert reconciled.origin == PositionOrigin.BROKER_ADOPTED
    assert second.position_management_profile(reconciled.position_id).trade_type == TradeType.BTST

    names = [e["name"] for e in second.events_snapshot()]
    assert "POSITION_ADOPTED" in names
    second.stop()
