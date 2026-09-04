from datetime import datetime, timezone

from trademonitor.adapters.google_sheet import GoogleSheetConfig, GoogleSheetRow, GoogleTopPicksAdapter
from trademonitor.core.manager import CoreTMManager
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


def test_sheet_observation_flows_through_canonical_tm_intake(tmp_path):
    repo = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    manager = CoreTMManager(repo)
    manager.start()
    try:
        cfg = GoogleSheetConfig(
            spreadsheet_id="sheet-x",
            service_account_file=tmp_path / "sa.json",
            state_file=tmp_path / "feed.json",
        )
        adapter = GoogleTopPicksAdapter(cfg)
        prepared = adapter.prepare_row(
            GoogleSheetRow(
                row_number=2,
                values={
                    "Instrument": "KAYNES",
                    "Direction": "BULLISH",
                    "Suggested Option": "KAYNES SEP 4200 CE",
                    "Timestamp": "2026-09-04 10:15:00",
                },
            ),
            fallback_observed_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
        )
        assert prepared is not None
        result = manager.ingest_trade_observation(**prepared.observation.submit_kwargs())
        counts = manager.intake_snapshot()
        assert result.outcome.identity["underlying"] == "KAYNES"
        assert counts["observations"] == 1
        assert counts["outcomes"] == 1
        assert counts["active_episodes"] == 1
    finally:
        manager.stop()
