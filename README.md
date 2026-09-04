# TradeMonitor

**Current milestone:** TM3/TGT4 — Exit Agents and Escalation

TradeMonitor is being developed as a professional trade-monitoring, risk-governance, position-management, and execution system for Indian markets.

The canonical design references are kept under `docs/`:

- `TradeMonitor_TM0_Architecture_Thesis.docx`
- `TRADEMONITOR_ROADMAP.md`
- `TradeMonitor_TM_Roadmap.docx`

## Current Status

**TM3 / TGT4 — Exit Agents and Escalation — COMPLETE**

TM1 and TM2 are complete. TM3 now includes deterministic managed-position rules:

- unified `MANAGED / UNMANAGED` Position universe and explicit adoption boundary
- deterministic SL / TP / TSL, profit-lock, spot/premium/P&L, time/horizon, and invalidation rules
- named rule-policy installation and explicit rule cancellation
- stateful trailing/profit-lock rules with durable arming/ratcheting state
- management-rule state survives restart
- triggered rules emit auditable `EXIT_REVIEW` signals only; they do not create ExecutionRequests
- broker truth remains authoritative and `UNMANAGED` positions remain read-only

**NO LIVE TRADING OR BROKER-WRITE CAPABILITY EXISTS IN TM3/TGT4.**

TM3/TGT4 now provides durable PAPER-only exit proposals, partial-exit shapes, duplicate/conflicting exit suppression, DAY end-of-day protection, deliberate position holding-intent conversion, and broker-truth closure convergence. Module M and real execution remain TM4 scope.


## Independent Program / Adapter Boundary

TradeMonitor is not tied to the original Google Sheets or scanners. External sources must translate their own formats through adapters into TM's canonical intake contract. Supported/intended integration styles include direct console input, Python, REST/web, Google Sheets, DayScanner/Positional Scanner, and user-defined adapters.

See:

- `docs/INTEGRATION_INTERFACE.md`
- `docs/SETUP_AND_ADAPTERS.md`
- `docs/GOOGLE_SHEET_INTERFACE.md`
- `docs/TM_SOURCE_INDEPENDENCE_AUDIT.md`

A different user should be able to configure their own source and broker adapters without adopting this project's workbook schemas.

## Development Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Run the development application:

```bash
python scripts/run_dev.py
```

By default the runtime database is stored at `data/trademonitor.db`. Override it with:

```bash
TM_DATABASE_PATH=/tmp/trademonitor.db python scripts/run_dev.py
```


### TM3/TGT4
Strategic exit proposals can now use the separate external Agents validation gate with `APPROVE / REJECT / RETREAT_WAIT`, User escalation on disagreement, and no broker-write capability. Protective/deterministic exits bypass the Agent gate.
