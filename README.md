# TradeMonitor

TradeMonitor is being developed as a professional trade-monitoring, risk-governance, position-management, and execution system for Indian markets.

The canonical design references are kept under `docs/`:

- `TradeMonitor_TM0_Architecture_Thesis.docx`
- `TRADEMONITOR_ROADMAP.md`
- `TradeMonitor_TM_Roadmap.docx`

## Current Status

**TM2 / TGT2 — Entry Monitoring and Trade Intent**

TM1 is frozen and complete. TM2/TGT1 established intake identity. TM2/TGT2 adds deterministic entry monitoring while preserving the PAPER/read-only boundary:

- immutable source observations with explicit `src_id`, source, datetime and provenance
- normalized broad Outcome identity
- time-relevant Episode identity for changing market/contract context
- exact observation de-duplication and restart-safe persistence
- same-source/different-outcome and different-source/same-outcome reconciliation
- existing broker-position awareness without implicit scale-in
- explicit bounded ambiguity-resolution port for the separate external Agents service
- Core trade context receives only summarized intake counts; Intake remains domain owner
- PAPER mode remains explicit; live execution remains disabled

**NO LIVE TRADING OR BROKER-WRITE CAPABILITY EXISTS IN TM2/TGT2.**

Entry trigger/confirmation logic, full Agent validation workflow, Risk Management entry gates, position-management policies, Exit Monitor, Module M, and real broker writes remain later roadmap targets.

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
