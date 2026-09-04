# TradeMonitor Integration Interface

## Purpose

TradeMonitor is an independent program. External systems may supply trade observations through adapters, but no TradeMonitor core domain is allowed to depend on the schema, worksheet names, column names, API payloads, or implementation details of any particular source.

The integration boundary is:

```text
External Source
    ↓
Source-Specific Adapter
    ↓
CanonicalTradeObservation
    ↓
TradeMonitor Intake
    ↓
Outcome → Episode → Entry pipeline
```

Examples of external sources include:

- interactive console input
- Python callers
- REST/JSON services
- Google Sheets
- DayScanner / Positional Scanner
- another user's custom application
- future adapters not yet designed

## Canonical Intake Contract

Every external source must be normalized into:

```text
src_id
source
observed_at
intent
raw_payload (optional provenance)
```

The normalized `intent` currently supports:

```text
underlying          required
direction           required
setup               required
trade_type          optional at generic intake; required later where the workflow needs it
instrument_type     optional at generic intake
option_type         optional
contract_symbol     optional
expiry              optional
strike              optional
premium             optional
reference_price     optional
context_key         optional
```

TradeMonitor treats `src_id` as source identity/provenance. It does not grant trading authority merely because a source repeats an idea.

## Source Independence Invariant

**No TradeMonitor core domain may read source-specific field names directly.**

For example, the following must never appear in core Intake/Entry/Risk/Position logic:

```text
Top Picks
Morning Dashboard
Suggested Option
CGPT Action
Sheet1!H:H
scanner-specific column numbers
```

Such names belong only inside the corresponding adapter.

## Generic Mapping Adapter

TradeMonitor provides `MappingTradeAdapter` as a minimal source-neutral helper. It can translate arbitrary external field names to the canonical intent fields.

Example:

```python
from datetime import datetime, timezone
from trademonitor.adapters import MappingTradeAdapter

adapter = MappingTradeAdapter({
    "underlying": "ticker",
    "direction": "bias",
    "setup": "entry_style",
    "trade_type": "holding",
    "instrument_type": "instrument",
    "option_type": "right",
    "contract_symbol": "contract",
    "expiry": "contract_expiry",
    "strike": "strike_px",
    "premium": "ltp",
})

observation = adapter.from_mapping(
    external_payload,
    src_id="MYAPP-20260904-001",
    source="MY_CUSTOM_APP",
    observed_at=datetime.now(timezone.utc),
)

result = tm.ingest_trade_observation(**observation.submit_kwargs())
```

A user's application therefore does not need to adopt another user's Google Sheet layout.

## Adapter Responsibilities

A source adapter owns:

- authentication/connectivity to its source
- source-specific parsing
- source-specific column/key names
- timestamp normalization
- conversion into the canonical TM contract
- validation of source-specific required values
- source-specific retry/error handling
- preserving the original payload as provenance when useful

A source adapter does **not** own:

- Outcome/Episode de-duplication
- entry decisions
- Risk Management
- position management
- exit decisions
- broker deployment

Those remain TradeMonitor domain responsibilities.

## Direct Console Use

TradeMonitor is intended to support direct console entry as one adapter/control surface. Manual entry can be tedious, but it remains important because it proves TM is usable without Google Sheets or any scanner.

The console adapter should ultimately gather the same canonical information and submit it through the same Intake boundary. It must not create a separate shortcut around Intake, Risk, Agents, or other domain rules.

## Google Sheets

Google Sheets is optional. A Google Sheet adapter may map any configured workbook format into the canonical contract. TradeMonitor core must remain unaware of workbook names and columns.

See `GOOGLE_SHEET_INTERFACE.md`.

## Python / REST / Web

Python callers can use the canonical adapter directly. A future REST/web adapter should expose the same logical contract and then call the same TM Intake boundary. Web UI is therefore a presentation/integration choice rather than a core dependency.

## Extensibility Rule

Adding a new source should normally require:

1. a new adapter or configuration for an existing generic adapter,
2. adapter-specific tests,
3. no modification to Intake/Entry/Risk/Position core logic unless the new source reveals a genuinely new domain concept.

If a new source requires core code to know its proprietary schema, the integration boundary has been violated.
