# Google Top Picks → EntryIntent PAPER Bridge Acceptance

Status: integration checkpoint after TM4/TGT1; not a new roadmap milestone.

## Purpose

Close the real-input PAPER path from the user's Google `Top Picks` sheet into the
existing generic TM Entry Monitor without coupling TM core to workbook columns.

## Implemented

- Source-specific translation lives under `trademonitor.adapters`.
- `BUY ON CONFIRM` can arm a canonical `EntryIntent`.
- `WAIT FOR PULLBACK` can arm a canonical `EntryIntent`.
- `AVOID CHASE` remains Intake-only and is not armed.
- Unknown/unverified Entry Status values are not guessed.
- Spot Entry Zone, Premium Entry Zone, Invalidation, expiry, strike and contract
  are translated into the existing generic EntryIntent contract.
- Source Confirmation text is preserved as provenance; no workbook-specific NLP
  logic was introduced into core Entry.
- DAY horizon is adapter-defined as the NSE session boundary for this DayScanner
  feeder.
- Existing active EntryIntent for an Episode is reused rather than duplicated.
- Unchanged Sheet rows can be re-resolved for EntryIntent backfill when
  `--create-entry-intents` is explicitly requested.

## Deliberately not implemented

- No market-data polling/streaming loop.
- No automatic evaluation of the created EntryIntents against live prices.
- No live Agents service.
- No live broker writes.
- No change to Module M simulation-only status in TM4/TGT1.

## Validation

- Full suite: 131 tests passed.
- `python -m compileall src scripts`: PASS.

## Trial command

```bash
python scripts/feed_google_top_picks.py --dry-run --limit 5 --create-entry-intents
python scripts/feed_google_top_picks.py --limit 5 --create-entry-intents
python scripts/run_dev.py
```

Expected control-room effect: Intake remains de-duplicated while eligible Top
Picks appear in Entry as `MONITORING`. They will remain there until a market-data
provider supplies `EntryMarketSnapshot` evaluations.
