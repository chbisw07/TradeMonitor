# TradeMonitor

TradeMonitor is being developed as a professional trade-monitoring, risk-governance, position-management, and execution system for Indian markets.

The canonical design references are kept under `docs/`:

- `TradeMonitor_TM0_Architecture_Thesis.docx`
- `TRADEMONITOR_ROADMAP.md`
- `TradeMonitor_TM_Roadmap.docx`

## Current Status

**TM1 / TGT2 — Broker Truth and Position Reconciliation**

TM1/TGT1 is frozen. TGT2 adds the read-only broker-truth and durable position-reconciliation foundation:

- Core TM Manager and canonical runtime contexts
- explicit synchronous event boundary and durable audit log
- SQLite persistence/restart foundation
- read-only Broker account snapshot contract
- deterministic `MockBroker` for PAPER/integration validation
- durable canonical broker positions
- unified `MANAGED` / `UNMANAGED` management status
- broker-discovered positions default to `UNMANAGED`
- broker quantity/state is accepted as truth during reconciliation
- existing management status/provenance is preserved
- positions survive restart and are reconciled again to broker reality
- unified console position/status view
- hard `UNMANAGED` read-only guard

**NO LIVE TRADING CAPABILITY EXISTS IN TM1/TGT2.**

Real broker authentication/adapters, adoption, Risk Management rules, trade intake/entry logic, Agents, position-management policies, Exit Monitor, and Module M execution are later targets per the roadmap.

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
