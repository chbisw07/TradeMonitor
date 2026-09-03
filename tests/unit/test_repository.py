"""Tests for SQLite runtime persistence."""

from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


def test_repository_round_trips_context_and_event(tmp_path) -> None:
    repository = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    repository.initialize()
    repository.save_context(
        {
            "name": "health",
            "version": 1,
            "updated_at": "2026-09-03T12:00:00+00:00",
            "data": {"core": "HEALTHY"},
        }
    )
    repository.append_event(
        {
            "event_id": "evt-1",
            "name": "TEST_EVENT",
            "occurred_at": "2026-09-03T12:00:00+00:00",
            "source": "TEST",
            "payload": {"ok": True},
        }
    )

    contexts = repository.load_contexts()
    events = repository.list_events()

    assert contexts[0]["data"] == {"core": "HEALTHY"}
    assert events[0]["name"] == "TEST_EVENT"
    assert events[0]["payload"] == {"ok": True}
