"""Deterministic read-only broker used by TM1/TGT2 tests and PAPER runtime."""

from __future__ import annotations

from threading import RLock

from trademonitor.brokers.base import Broker
from trademonitor.domain.models import BrokerAccountSnapshot


class MockBroker(Broker):
    """In-memory broker truth source with no order-placement capability."""

    def __init__(self, snapshot: BrokerAccountSnapshot | None = None, *, name: str = "MOCK") -> None:
        self._name = name
        self._snapshot = snapshot or BrokerAccountSnapshot.create(broker=name)
        self._lock = RLock()

    @property
    def name(self) -> str:
        return self._name

    def set_snapshot(self, snapshot: BrokerAccountSnapshot) -> None:
        if snapshot.broker != self._name:
            raise ValueError(
                f"Snapshot broker {snapshot.broker!r} does not match adapter {self._name!r}"
            )
        with self._lock:
            self._snapshot = snapshot

    def fetch_account_snapshot(self) -> BrokerAccountSnapshot:
        with self._lock:
            return self._snapshot
