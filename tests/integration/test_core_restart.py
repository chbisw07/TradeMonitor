"""Integration tests for TM1/TGT1 persistence and restart semantics."""

from trademonitor.core.manager import CoreTMManager
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


def build_manager(path) -> CoreTMManager:
    return CoreTMManager(SQLiteRuntimeRepository(Database(path)))


def test_core_restores_context_after_restart(tmp_path) -> None:
    db_path = tmp_path / "tm.db"

    first = build_manager(db_path)
    first.start()
    first.patch_context("market", {"feed": "HEALTHY", "symbol_count": 120}, source="TEST")
    version_before_stop = first.contexts.get("market").version
    first.stop()

    second = build_manager(db_path)
    second.start()

    market = second.contexts.get("market")
    assert market.data == {"feed": "HEALTHY", "symbol_count": 120}
    assert market.version == version_before_stop
    assert second.contexts.get("health").data["live_execution_enabled"] is False

    second.stop()


def test_context_mutation_is_audited(tmp_path) -> None:
    repository = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    manager = CoreTMManager(repository)
    manager.start()

    manager.patch_context("risk", {"status": "HEALTHY"}, source="RISK")

    event_names = [event["name"] for event in repository.list_events()]
    assert "CORE_STARTED" in event_names
    assert "CONTEXT_UPDATED" in event_names

    manager.stop()
