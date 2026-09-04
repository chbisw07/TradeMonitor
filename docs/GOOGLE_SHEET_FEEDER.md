# Google Top Picks PAPER Feeder

## Purpose

`scripts/feed_google_top_picks.py` is a **read-only Google Sheets integration harness** for observing real scanner candidates inside TradeMonitor without connecting a live execution broker.

It is intentionally outside TM core:

```text
Google Sheet (Top Picks)
        ↓
GoogleTopPicksAdapter
        ↓
CanonicalTradeObservation
        ↓
TM Intake
        ↓
Outcome → Episode
```

The feeder does **not** create broker orders and has no path to a broker execution adapter.

## Install optional Google support

From the TradeMonitor virtual environment:

```bash
pip install -e '.[google]'
```

## Configure `.env`

Copy the placeholders from `.env.example` and set at least:

```env
GOOGLE_SPREADSHEET_ID=<spreadsheet-id>
GOOGLE_SERVICE_ACCOUNT_FILE=/absolute/path/to/service-account.json
GOOGLE_SHEET_NAME=Top Picks
```

The same Google service-account credential already used by another scanner/bridge may be referenced by absolute path. Do not copy credentials into the repository and do not commit `.env`.

## First run: dry-run only

```bash
python scripts/feed_google_top_picks.py --dry-run --limit 5
```

This authenticates, reads the configured sheet, maps rows, and prints the canonical observations. It does **not** write TradeMonitor state.

If the mapping looks correct, run:

```bash
python scripts/feed_google_top_picks.py --limit 5
```

Then inspect TM:

```bash
python scripts/run_dev.py
```

The Intake counts should now reflect persisted observations/outcomes/episodes.

## Re-run behavior

The feeder stores an adapter-local fingerprint file (default `data/google_top_picks_state.json`). Unchanged rows are skipped on subsequent runs so repeatedly reading the same Sheet does not manufacture new source observations merely because the feeder ran later.

Use `--force` only for diagnostics when you deliberately want to submit unchanged rows again.

## Header aliases

The adapter recognizes common headers without exposing any of them to TM core. Examples include:

- Underlying: `Underlying`, `Symbol`, `Stock`, `Instrument`, `Ticker`
- Direction: `Direction`, `Bias`, `Side`, `View`
- Contract: `Suggested Option`, `Option Contract`, `Contract`, `Option`
- Trade Type: `Trade Type`, `Holding`
- Premium: `Premium`, `Option Premium`, `Premium Entry Zone`
- Spot/reference: `Spot`, `Spot Price`, `Underlying LTP`, `LTP`
- Timestamp: `Timestamp`, `Date Time`, `Scan Time`, `Run Time`

If Direction is absent, a CE contract implies `BULLISH` and a PE contract implies `BEARISH` for this Top Picks adapter.

If Setup is absent, the configured default `TOP_PICK` is used. If Trade Type is absent, the configured default `DAY` is used. These defaults are adapter configuration, not TM core rules.

## Scope of this trial

This feeder currently validates the **intake/de-duplication boundary** with real Google Sheet data. It preserves the complete source row as provenance.

It does not automatically construct detailed EntryIntent trigger/confirmation rules from workbook-specific columns. That can be added as a later source-specific adapter enhancement once the real Top Picks rows have been observed and their semantics verified.
