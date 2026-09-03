"""Broker failure should degrade broker capability without collapsing Core."""

from pathlib import Path

import pytest

from trademonitor.brokers.base import Broker
from trademonitor.core.manager import CoreTMManager
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


class FailingBroker(Broker):
    @property
    def name(self) -> str:
        return "FAILBROKER"

    def fetch_account_snapshot(self):
        raise ConnectionError("simulated broker outage")


def test_broker_failure_is_visible_and_core_remains_healthy(tmp_path: Path) -> None:
    manager = CoreTMManager(SQLiteRuntimeRepository(Database(tmp_path / "tm.db")))
    manager.start()

    with pytest.raises(ConnectionError):
        manager.reconcile_broker_truth(FailingBroker())

    health = manager.contexts.get("health").data["domains"]
    assert health["BROKER"]["status"] == "DEGRADED"
    assert health["CORE"]["status"] == "HEALTHY"
    assert manager.contexts.get("broker").data["status"] == "UNAVAILABLE"
    assert any(item.source == "BROKER" for item in manager.attention_snapshot())
    manager.stop()
