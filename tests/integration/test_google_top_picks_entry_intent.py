from datetime import datetime, timezone

from trademonitor.adapters import CanonicalTradeObservation, translate_top_pick_to_entry
from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.models import NormalizedTradeIntent
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


def test_realistic_top_pick_can_flow_from_intake_to_entry_monitoring(tmp_path):
    manager = CoreTMManager(SQLiteRuntimeRepository(Database(tmp_path / "tm.db")))
    manager.start()
    try:
        observation = CanonicalTradeObservation(
            src_id="GS-X-R7-CE",
            source="GOOGLE_TOP_PICKS",
            observed_at=datetime(2026, 9, 4, 6, 0, tzinfo=timezone.utc),
            intent=NormalizedTradeIntent(
                underlying="HDFCLIFE",
                direction="BULLISH",
                setup="TOP_PICK",
                trade_type="DAY",
                instrument_type="OPTION",
                option_type="CE",
                contract_symbol="2026-09-29 545 CE @ 13.50 | Δ 0.561",
                expiry="2026-09-29",
                strike="545",
                premium="₹12.42–₹14.35",
                reference_price="544.28–545.34",
            ),
            raw_payload={
                "entry_status": "BUY ON CONFIRM",
                "confirmation": "15m bullish hold/reversal; avoid entry on a weak close",
                "invalidation": "541.86",
            },
        )
        intake = manager.ingest_trade_observation(**observation.submit_kwargs())
        translation = translate_top_pick_to_entry(observation)
        assert translation.arm
        entry = manager.create_entry_intent(episode=intake.episode, **dict(translation.kwargs or {}))
        assert entry.state.value == "MONITORING"
        assert len(manager.entry_snapshot()) == 1
    finally:
        manager.stop()
