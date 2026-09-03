"""TM1/TGT3 operator Attention queue tests."""

from pathlib import Path

from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.enums import AttentionLevel
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


def _manager(tmp_path: Path) -> CoreTMManager:
    return CoreTMManager(SQLiteRuntimeRepository(Database(tmp_path / "tm.db")))


def test_attention_queue_is_durable_and_resolvable(tmp_path: Path) -> None:
    db = tmp_path / "tm.db"
    first = CoreTMManager(SQLiteRuntimeRepository(Database(db)))
    first.start()
    item = first.add_attention(
        level=AttentionLevel.ATTENTION,
        source="ENTRY",
        title="User decision required",
        detail="Agent returned RETREAT_WAIT",
    )
    first.stop()

    restarted = CoreTMManager(SQLiteRuntimeRepository(Database(db)))
    restarted.start()
    restored = restarted.attention_snapshot()
    assert [i.attention_id for i in restored] == [item.attention_id]

    restarted.resolve_attention(item.attention_id, source="USER")
    assert restarted.attention_snapshot() == []
    all_items = restarted.attention_snapshot(active_only=False)
    assert all_items[0].status == "RESOLVED"
    restarted.stop()
