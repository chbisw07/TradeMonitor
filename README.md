# TradeMonitor

TradeMonitor is being developed as a professional trade-monitoring, risk-governance, position-management, and execution system for Indian markets.

The canonical design references are kept under `docs/`:

- `TradeMonitor_TM0_Architecture_Thesis.docx`
- `TRADEMONITOR_ROADMAP.md`
- `TradeMonitor_TM_Roadmap.docx`

## Current Status

**TM1 / TGT1 — Core TM Manager and Runtime Contexts**

Implemented in this target:

- Core TM Manager coordination foundation
- canonical runtime contexts: broker, market, trade, position, risk, decision, health
- explicit synchronous event bus
- structured immutable runtime events
- SQLite persistence for context snapshots and event audit records
- restart/context restoration foundation
- concise console status view
- unit/integration tests for persistence, event flow, restart, and safety status

**NO LIVE TRADING CAPABILITY EXISTS IN TM1/TGT1.**

Broker truth reconciliation, actual trade intake, Risk Management rules, Agent integration, position management, and Module M execution are later targets per the roadmap.

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
