# TradeMonitor

TradeMonitor is being developed as a professional trade-monitoring, risk-governance, position-management, and execution system for Indian markets.

The canonical design references are kept under `docs/`:

- `TradeMonitor_TM0_Architecture_Thesis.docx`
- `TRADEMONITOR_ROADMAP.md`
- `TradeMonitor_TM_Roadmap.docx`

## Current Status

**TM3 / TGT2 — Deterministic Management Rules — COMPLETE**

TM1 and TM2 are complete. TM3 now includes deterministic managed-position rules:

- unified `MANAGED / UNMANAGED` Position universe and explicit adoption boundary
- deterministic SL / TP / TSL, profit-lock, spot/premium/P&L, time/horizon, and invalidation rules
- named rule-policy installation and explicit rule cancellation
- stateful trailing/profit-lock rules with durable arming/ratcheting state
- management-rule state survives restart
- triggered rules emit auditable `EXIT_REVIEW` signals only; they do not create ExecutionRequests
- broker truth remains authoritative and `UNMANAGED` positions remain read-only

**NO LIVE TRADING OR BROKER-WRITE CAPABILITY EXISTS IN TM3/TGT2.**

Exit proposals, partial exits, duplicate-exit suppression, and position conversion belong to TM3/TGT3. Module M and real execution remain TM4 scope.

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
