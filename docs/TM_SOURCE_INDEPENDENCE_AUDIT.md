# TradeMonitor Source-Independence Audit

## Reason

This audit was performed after the architectural requirement was made explicit that TradeMonitor must be independently usable by another user without requiring the original Google Sheet, DayScanner, Positional Scanner, or their particular formats.

## Result

The current TM3/TGT4 core is structurally source-independent.

Observed findings:

- Intake accepts generic `src_id`, `source`, timestamp, normalized trade intent, and optional raw provenance.
- Outcome/Episode logic does not import or depend on Google Sheets.
- Entry, Risk, Position/Exit, Core, and broker-reconciliation domains do not depend on named scanner columns or worksheet names.
- The existing Google Sheet code is only a placeholder package and is not imported by core trading domains.
- Scanner-like names appear in tests only as sample `source` values/provenance.
- Agents remain behind an external gateway rather than source-specific intake logic.

## Hardening Added

- Added `CanonicalTradeObservation` as the documented source-neutral adapter handoff object.
- Added `MappingTradeAdapter` to demonstrate arbitrary external-schema normalization without changing TM core.
- Added `INTEGRATION_INTERFACE.md`.
- Reframed `GOOGLE_SHEET_INTERFACE.md` explicitly as an optional adapter boundary.
- Added `SETUP_AND_ADAPTERS.md`.
- Added tests showing canonical and arbitrary external payloads can enter through the same source-neutral contract.

## Architectural Invariant

> No TradeMonitor core domain may depend on the schema, column names, worksheet names, payload layout, or implementation details of a particular external trade source. Every source must cross an adapter boundary into TradeMonitor's canonical intake contract.

## Consequence

Another user can use TradeMonitor through console/Python/REST/web or their own Sheet/scanner adapter. The original project owner's Sheets/scanners are optional integrations, not prerequisites.
