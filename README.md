# TradeMonitor

TradeMonitor is being developed as a professional trade-monitoring, risk-governance, position-management, and execution system for Indian markets.

The canonical design references are kept under `docs/`:

- `TradeMonitor_TM0_Architecture_Thesis.docx`
- `TRADEMONITOR_ROADMAP.md`
- `TradeMonitor_TM_Roadmap.docx`

## Current Status

**TM3 / TGT1 — Position Manager and Adoption — COMPLETE**

TM1 and TM2 are complete. TM3 now begins the managed-position lifecycle:

- one unified broker-reconciled Position universe
- explicit `MANAGED / UNMANAGED` authority boundary
- broker-discovered positions remain `UNMANAGED` and read-only by default
- explicit adoption requires current-runtime broker truth and sufficient management context
- adopted positions receive durable asset/instrument/trade type, horizon, and F&O expiry metadata
- adoption changes only TM management authority/provenance; broker quantity/state/average price remain broker truth
- adopted positions survive restart and continue to reconcile to broker truth
- future TM-native and adopted positions are designed to converge on the same downstream management machinery

**NO LIVE TRADING OR BROKER-WRITE CAPABILITY EXISTS IN TM3/TGT1.**

SL/TP/TSL and deterministic management rules begin in TM3/TGT2. Module M and real execution remain TM4 scope.

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
