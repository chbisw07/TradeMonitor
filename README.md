# TradeMonitor

TradeMonitor is being developed as a professional trade-monitoring, risk-governance, position-management, and execution system for Indian markets.

The canonical design references are kept under `docs/`:

- `TradeMonitor_TM0_Architecture_Thesis.docx`
- `TRADEMONITOR_ROADMAP.md`
- `TradeMonitor_TM_Roadmap.docx`

## Current Status

**TM1 / TGT4 — PAPER Runtime, Recovery & Replay Validation**

TM1/TGT1–TGT3 are frozen. TGT4 validates the complete TM1 PAPER runtime under recovery, replay, freshness, and degraded-mode scenarios:

- Core TM Manager and canonical runtime contexts
- explicit synchronous event boundary and durable audit log
- SQLite persistence/restart foundation
- read-only Broker account snapshot contract and broker-truth reconciliation
- unified `MANAGED` / `UNMANAGED` positions
- vertical nearest-owner fault containment and escalation
- horizontal peer-domain fault isolation
- domain health states and capability-specific impact reporting
- durable operator Attention queue
- unified control-room view for health, Positions, and Attention
- PAPER mode made explicit; live execution remains disabled
- stale/out-of-order broker observations cannot overwrite newer truth
- exact event/snapshot replay is idempotent at the business-state boundary
- ungraceful restart and broker-offline-change recovery are validated
- repeated outage Attention is de-duplicated and resolved on recovery

**NO LIVE TRADING CAPABILITY EXISTS IN TM1/TGT4.**

Real broker authentication/adapters, adoption management, Risk Management policies, trade intake/entry logic, Agents integration, position-management policies, Exit Monitor, and Module M execution remain later roadmap targets.

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
