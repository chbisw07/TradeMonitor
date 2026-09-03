from datetime import UTC, datetime, timedelta

from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.models import NormalizedTradeIntent
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


def build(path):
    return CoreTMManager(SQLiteRuntimeRepository(Database(path)))


def test_intake_outcome_episode_identity_survives_restart(tmp_path):
    db = tmp_path / "tm.db"
    t = datetime(2026, 9, 3, 10, 15, tzinfo=UTC)
    intent = NormalizedTradeIntent(
        underlying="PNB", direction="BULLISH", setup="BREAKOUT", trade_type="BTST",
        instrument_type="OPTION", option_type="CE", contract_symbol="PNB26SEP117CE",
        expiry="2026-09-29", strike="117", premium="4.85",
    )
    first = build(db); first.start()
    a = first.ingest_trade_observation(src_id="PS-1", source="POSITIONAL_SCANNER", observed_at=t, intent=intent)
    first.stop()

    second = build(db); second.start()
    b = second.ingest_trade_observation(src_id="USER-2", source="USER", observed_at=t + timedelta(minutes=10), intent=intent)

    assert a.outcome.outcome_id == b.outcome.outcome_id
    assert a.episode.episode_id == b.episode.episode_id
    assert second.intake_snapshot() == {"observations": 2, "outcomes": 1, "episodes": 1, "active_episodes": 1}
    assert second.contexts.get("trade").data["intake"]["outcomes"] == 1
    second.stop()
