# TradeMonitor

TradeMonitor is being developed as a professional trade-monitoring, risk-governance, position-management, and execution system for Indian markets.

The canonical design references are kept under `docs/`:

- `TradeMonitor_TM0_Architecture_Thesis.docx`
- `TRADEMONITOR_ROADMAP.md`
- `TradeMonitor_TM_Roadmap.docx`

## Current Status

**TM1 / TGT3 — Health, Fault Containment and Control Room**

TM1/TGT1 and TGT2 are frozen. TGT3 adds the operational health/fault architecture and professional control-room baseline:

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

**NO LIVE TRADING CAPABILITY EXISTS IN TM1/TGT3.**

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
