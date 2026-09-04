# Google Sheet PAPER Feeder — Acceptance Record

This is an integration-harness checkpoint layered on the frozen TM4/TGT1 architecture. It is not a new roadmap milestone.

## Added

- optional read-only Google Sheets client boundary (`gspread` extra)
- flexible Top Picks adapter that normalizes common headers into `CanonicalTradeObservation`
- local adapter state to skip unchanged rows across feeder runs
- `scripts/feed_google_top_picks.py` with dry-run and PAPER-intake modes
- `.env.example` placeholders and setup documentation
- unit/integration tests proving the Google-specific schema stops at the adapter boundary

## Preserved invariants

- Google Sheets remains optional
- TM core does not import Google-specific schema names
- feeder has no broker-write path
- Module M remains simulation-only at TM4/TGT1
- unchanged rows cannot silently manufacture repeated intake solely because the feeder ran again

## Validation

- `PYTHONPATH=src pytest -q` → 125 passed
- `python -m compileall -q src scripts` → PASS
- feeder without config exits safely with a clear configuration error
