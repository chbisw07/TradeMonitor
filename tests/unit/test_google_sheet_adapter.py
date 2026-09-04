from datetime import datetime, timezone
from pathlib import Path

from trademonitor.adapters.google_sheet import (
    FeederState,
    GoogleSheetConfig,
    GoogleSheetRow,
    GoogleTopPicksAdapter,
    load_dotenv_file,
)


def config(tmp_path: Path) -> GoogleSheetConfig:
    return GoogleSheetConfig(
        spreadsheet_id="sheet-123",
        service_account_file=tmp_path / "service.json",
        sheet_name="Top Picks",
        state_file=tmp_path / "state.json",
    )


def test_top_picks_maps_common_headers_and_infers_ce_direction(tmp_path):
    adapter = GoogleTopPicksAdapter(config(tmp_path))
    prepared = adapter.prepare_row(
        GoogleSheetRow(
            row_number=2,
            values={
                "Instrument": "KAYNES",
                "Suggested Option": "KAYNES SEP 4200 CE",
                "Trade Type": "DAY",
                "Premium Entry Zone": "130-145",
                "Spot": "4142.5",
                "Timestamp": "2026-09-04 10:15:00",
            },
        )
    )
    assert prepared is not None
    obs = prepared.observation
    assert obs.intent.underlying == "KAYNES"
    assert obs.intent.direction == "BULLISH"
    assert obs.intent.option_type == "CE"
    assert obs.intent.strike == "4200"
    assert obs.intent.premium == "130-145"
    assert obs.intent.reference_price == "4142.5"
    assert obs.intent.setup == "TOP_PICK"
    assert obs.src_id.endswith("-R2")


def test_top_picks_infers_bearish_from_pe(tmp_path):
    adapter = GoogleTopPicksAdapter(config(tmp_path))
    prepared = adapter.prepare_row(
        GoogleSheetRow(
            row_number=9,
            values={"Symbol": "DRREDDY", "Suggested Option": "DRREDDY SEP 1180 PE"},
        ),
        fallback_observed_at=datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc),
    )
    assert prepared is not None
    assert prepared.observation.intent.direction == "BEARISH"
    assert prepared.observation.intent.option_type == "PE"


def test_explicit_direction_and_source_id_win(tmp_path):
    adapter = GoogleTopPicksAdapter(config(tmp_path))
    prepared = adapter.prepare_row(
        GoogleSheetRow(
            row_number=3,
            values={
                "SRC": "MY-SCAN-77",
                "Underlying": "PNB",
                "Direction": "bullish",
                "Setup": "breakout",
                "Suggested Option": "PNB SEP 117 CE",
            },
        ),
        fallback_observed_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
    )
    assert prepared is not None
    assert prepared.observation.src_id == "MY-SCAN-77"
    assert prepared.observation.intent.setup == "BREAKOUT"


def test_disabled_row_is_not_prepared(tmp_path):
    adapter = GoogleTopPicksAdapter(config(tmp_path))
    prepared = adapter.prepare_row(
        GoogleSheetRow(
            row_number=4,
            values={"Symbol": "PNB", "Direction": "BULLISH", "Active": "NO"},
        )
    )
    assert prepared is None


def test_feeder_state_round_trip(tmp_path):
    path = tmp_path / "state.json"
    state = FeederState(path)
    assert not state.unchanged("row-1", "abc")
    state.remember("row-1", "abc")
    state.save()
    restored = FeederState(path)
    assert restored.unchanged("row-1", "abc")
    assert not restored.unchanged("row-1", "def")


def test_load_dotenv_file(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_SPREADSHEET_ID", raising=False)
    env = tmp_path / ".env"
    env.write_text("GOOGLE_SPREADSHEET_ID=abc123\nGOOGLE_SHEET_NAME='Top Picks'\n")
    assert load_dotenv_file(env)
    import os
    assert os.environ["GOOGLE_SPREADSHEET_ID"] == "abc123"
    assert os.environ["GOOGLE_SHEET_NAME"] == "Top Picks"
