"""TM1/TGT4 PAPER recovery/replay acceptance scenarios."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from trademonitor.brokers.base import Broker
from trademonitor.brokers.mock import MockBroker
from trademonitor.core.event_bus import EventBus
from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.enums import ManagementStatus
from trademonitor.domain.events import DomainEvent
from trademonitor.domain.models import BrokerAccountSnapshot, BrokerPositionSnapshot
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository
from trademonitor.positions.manager import PositionManager, UnmanagedPositionError


def build_manager(path, event_bus: EventBus | None = None) -> CoreTMManager:
    return CoreTMManager(SQLiteRuntimeRepository(Database(path)), event_bus=event_bus)


def broker_snapshot(*, observed_at: datetime, qty: int = 50, ltp: str = "5.20") -> BrokerAccountSnapshot:
    return BrokerAccountSnapshot.create(
        broker="MOCK",
        observed_at=observed_at,
        positions=[
            BrokerPositionSnapshot(
                broker="MOCK",
                broker_position_key="NFO:PNB26SEP117CE:NRML",
                exchange="NFO",
                symbol="PNB26SEP117CE",
                product="NRML",
                quantity=qty,
                average_price="4.85",
                last_price=ltp,
                observed_at=observed_at,
            )
        ],
    )


def test_exact_event_replay_is_idempotent_and_not_republished(tmp_path) -> None:
    bus = EventBus()
    received: list[str] = []
    bus.subscribe_all(lambda event: received.append(event.event_id))
    repository = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    manager = CoreTMManager(repository, event_bus=bus)
    manager.start()

    event = DomainEvent.create("REPLAY_TEST", source="TEST", payload={"value": 7})
    manager.publish(event)
    manager.publish(DomainEvent.from_record(event.to_record()))

    stored = [item for item in repository.list_events() if item["event_id"] == event.event_id]
    assert len(stored) == 1
    assert received.count(event.event_id) == 1
    manager.stop()


def test_older_broker_snapshot_cannot_overwrite_newer_truth(tmp_path) -> None:
    manager = build_manager(tmp_path / "tm.db")
    t1 = datetime(2026, 9, 3, 10, 15, tzinfo=UTC)
    newer = broker_snapshot(observed_at=t1 + timedelta(minutes=5), qty=40, ltp="5.40")
    older = broker_snapshot(observed_at=t1, qty=99, ltp="4.00")
    broker = MockBroker(newer)
    manager.start()
    manager.reconcile_broker_truth(broker)

    broker.set_snapshot(older)
    manager.reconcile_broker_truth(broker)

    position = manager.positions_snapshot(open_only=True)[0]
    assert position.quantity == 40
    assert str(position.last_price) == "5.40"
    ignored = [e for e in manager.events_snapshot() if e["name"] == "BROKER_SNAPSHOT_IGNORED"]
    assert ignored[-1]["payload"]["relation"] == "STALE"
    manager.stop()


def test_exact_broker_snapshot_replay_keeps_same_business_state(tmp_path) -> None:
    db_path = tmp_path / "tm.db"
    observed = datetime(2026, 9, 3, 10, 15, tzinfo=UTC)
    broker = MockBroker(broker_snapshot(observed_at=observed, qty=50))

    first = build_manager(db_path)
    first.start()
    first.reconcile_broker_truth(broker)
    fingerprint_before = first.runtime_fingerprint()
    position_id = first.positions_snapshot(open_only=True)[0].position_id
    first.stop()

    second = build_manager(db_path)
    second.start()
    second.reconcile_broker_truth(broker)  # exact replay of already accepted broker truth
    fingerprint_after = second.runtime_fingerprint()
    position = second.positions_snapshot(open_only=True)[0]

    assert fingerprint_after == fingerprint_before
    assert position.position_id == position_id
    assert position.management_status == ManagementStatus.UNMANAGED
    replay_events = [e for e in second.events_snapshot() if e["name"] == "BROKER_SNAPSHOT_IGNORED"]
    assert replay_events[-1]["payload"]["relation"] == "REPLAY"
    second.stop()


def test_ungraceful_restart_restores_durable_context_then_reconciles_new_broker_truth(tmp_path) -> None:
    db_path = tmp_path / "tm.db"
    t1 = datetime(2026, 9, 3, 10, 15, tzinfo=UTC)
    broker = MockBroker(broker_snapshot(observed_at=t1, qty=50))

    crashed = build_manager(db_path)
    crashed.start()
    crashed.patch_context("market", {"status": "HEALTHY", "symbol_count": 120}, source="TEST")
    crashed.reconcile_broker_truth(broker)
    # Simulate process loss: deliberately do not call stop().

    broker.set_snapshot(broker_snapshot(observed_at=t1 + timedelta(minutes=10), qty=25, ltp="5.60"))
    recovered = build_manager(db_path)
    recovered.start()
    assert recovered.contexts.get("market").data["symbol_count"] == 120
    recovered.reconcile_broker_truth(broker)

    position = recovered.positions_snapshot(open_only=True)[0]
    assert position.quantity == 25
    assert str(position.last_price) == "5.60"
    recovered.stop()


class FailingBroker(Broker):
    @property
    def name(self) -> str:
        return "MOCK"

    def fetch_account_snapshot(self):
        raise ConnectionError("simulated outage")


def test_broker_degraded_then_recovered_clears_operator_attention(tmp_path) -> None:
    manager = build_manager(tmp_path / "tm.db")
    manager.start()

    with pytest.raises(ConnectionError):
        manager.reconcile_broker_truth(FailingBroker())
    assert any(item.title == "Broker reconciliation unavailable" for item in manager.attention_snapshot())
    assert manager.contexts.get("health").data["domains"]["BROKER"]["status"] == "DEGRADED"

    observed = datetime(2026, 9, 3, 10, 15, tzinfo=UTC)
    manager.reconcile_broker_truth(MockBroker(broker_snapshot(observed_at=observed)))

    assert not any(item.title == "Broker reconciliation unavailable" for item in manager.attention_snapshot())
    assert manager.contexts.get("health").data["domains"]["BROKER"]["status"] == "HEALTHY"
    manager.stop()


def test_repeated_same_broker_failure_does_not_spam_attention_queue(tmp_path) -> None:
    manager = build_manager(tmp_path / "tm.db")
    manager.start()
    for _ in range(3):
        with pytest.raises(ConnectionError):
            manager.reconcile_broker_truth(FailingBroker())

    broker_items = [
        item for item in manager.attention_snapshot() if item.title == "Broker reconciliation unavailable"
    ]
    assert len(broker_items) == 1
    manager.stop()


def test_stale_market_context_degrades_only_market_domain(tmp_path) -> None:
    manager = build_manager(tmp_path / "tm.db")
    manager.start()
    manager.mark_context_stale(
        "market",
        domain="MARKET",
        reason="Market feed heartbeat expired",
        impact=("new price-dependent decisions unavailable",),
    )

    assert manager.contexts.get("market").data["status"] == "STALE"
    domains = manager.contexts.get("health").data["domains"]
    assert domains["MARKET"]["status"] == "DEGRADED"
    assert domains["CORE"]["status"] == "HEALTHY"
    manager.stop()


def test_unmanaged_boundary_survives_restart_and_reconciliation(tmp_path) -> None:
    db_path = tmp_path / "tm.db"
    observed = datetime(2026, 9, 3, 10, 15, tzinfo=UTC)
    broker = MockBroker(broker_snapshot(observed_at=observed))
    first = build_manager(db_path)
    first.start()
    first.reconcile_broker_truth(broker)
    first.stop()

    second = build_manager(db_path)
    second.start()
    position = second.positions_snapshot(open_only=True)[0]
    assert position.management_status == ManagementStatus.UNMANAGED
    with pytest.raises(UnmanagedPositionError):
        PositionManager.require_managed(position)
    second.stop()


def test_tm1_broker_contract_exposes_no_write_operations() -> None:
    public = {name for name in dir(Broker) if not name.startswith("_")}
    assert "fetch_account_snapshot" in public
    forbidden = {"place_order", "modify_order", "cancel_order", "exit_position", "submit_order"}
    assert public.isdisjoint(forbidden)
