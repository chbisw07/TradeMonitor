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

As of TM3/TGT4:

- the canonical core intake boundary exists,
- a source-neutral mapping adapter exists,
- Google Sheets remains an optional placeholder integration,
- no real broker write/execution capability exists yet,
- the actual external Agents service is not implemented inside TM.

More user-facing setup commands and concrete adapters can evolve without changing the core architecture.
