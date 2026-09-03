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

## TM2/TGT3 — External Agents Validation Gate

TradeMonitor now supports a bounded entry-validation handoff to a **separate external Agents service**. The Entry domain sends a structured review packet only after deterministic entry monitoring reaches `READY_FOR_REVIEW`. Agents must return exactly one verdict: `APPROVE`, `REJECT`, or `RETREAT_WAIT`, with an optional suggestion.

- `APPROVE` advances the entry only to `READY_FOR_RISK`.
- `REJECT` or `RETREAT_WAIT` never silently decides the trade; they escalate to the User, who chooses `APPROVE`, `REJECT`, or `RETREAT_WAIT`.
- Agent failure/unavailability also escalates to the User and never implies approval.
- Suggestions are persisted as advice only; they cannot create broker actions or bypass the normal Entry/Risk flow.
- Agents do not own TradeMonitor state and have no access to Module M or broker execution.

**There is still no live broker-write capability in TM2/TGT3.**
