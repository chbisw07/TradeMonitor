# TradeMonitor Setup and Adapter Model

TradeMonitor is designed to be independently installable and usable without the original developer's scanners or Google Sheets.

## Minimal Installation Concept

A usable installation needs:

- TradeMonitor core
- persistent local state
- a market-data provider when market-driven monitoring is required
- a broker adapter when broker truth/reconciliation is required
- at least one way to provide trade observations (console, Python, REST/web, Google Sheet, scanner adapter, etc.)

Optional services include:

- Google Sheets
- DayScanner / Positional Scanner adapters
- external Agents service
- web UI

## Example Installations

### Scanner/Sheet-heavy installation

```text
DayScanner ─┐
Positional ─┼─→ adapters → TradeMonitor
G.Sheet ────┘
Agents service optional
Broker adapter configured separately
```

### Friend / independent user

```text
Console or Python/REST adapter
            ↓
       TradeMonitor
            ↓
      configured broker
```

No original scanner workbook is required.

## Configuration Principle

Source-specific settings belong to the source adapter. Broker credentials/settings belong to broker adapters. Risk settings belong to versioned Risk Management configuration. TradeMonitor core should not embed installation-specific values.

## Current Development State

As of TM4/TGT1 plus the source-integration harness:

- the canonical core intake boundary exists,
- a source-neutral mapping adapter exists,
- Google Sheets remains optional; a read-only PAPER Top Picks feeder is available,
- no real broker write/execution capability exists yet,
- the actual external Agents service is not implemented inside TM.

More user-facing setup commands and concrete adapters can evolve without changing the core architecture.


## Google Sheet PAPER trial

See `GOOGLE_SHEET_FEEDER.md`. Install optional support with `pip install -e '.[google]'`, then follow the feeder guide.
