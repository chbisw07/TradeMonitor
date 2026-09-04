# Google Sheet Interface

Google Sheets is an **optional external adapter**, not a TradeMonitor core dependency.

TradeMonitor must never depend directly on workbook names, sheet names, column positions, or the user's DayScanner/Positional Scanner layouts.

The intended boundary is:

```text
Google Workbook / Sheet
        ↓
GoogleSheetTradeAdapter
        ↓
CanonicalTradeObservation
        ↓
TradeMonitor Intake
```

A future Google Sheet adapter may be configurable with mappings such as:

```text
external column           canonical field
------------------------------------------------
Instrument / Symbol   →   underlying
Bias / Direction      →   direction
Trade Type            →   trade_type
Suggested Option      →   contract_symbol
Expiry                →   expiry
Premium               →   premium
```

The exact workbook schema belongs to that adapter/configuration only.

Different users may therefore use different Google Sheet formats without changing the TradeMonitor core.

No live Google Sheets ingestion is implemented at the current milestone. See `INTEGRATION_INTERFACE.md` for the canonical interface and adapter responsibilities.
