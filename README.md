# TradeMonitor

TradeMonitor is being developed as a professional trade-monitoring, risk-governance, position-management, and execution system for Indian markets.

The canonical design references are kept under `docs/`:

- `TradeMonitor_TM0_Architecture_Thesis.docx`
- `TRADEMONITOR_ROADMAP.md`
- `TradeMonitor_TM_Roadmap.docx`

## Current Status

**TM2 / TGT4 — Risk Management Entry Gate — COMPLETE**

TM1 is frozen and complete. TM2 now implements the full PAPER-mode entry-decision path:

- source-aware Trade Intake with Outcome/Episode/time relevance and de-duplication
- deterministic Entry Monitoring with trigger/confirmation/invalidation and DAY/BTST/STBT/POS intent
- separate external Agents validation gate with `APPROVE / REJECT / RETREAT_WAIT` and User escalation
- highest-authority Risk Management entry gate with deterministic `PASS / BLOCK`
- account/portfolio visibility including `UNMANAGED` broker positions without violating their read-only boundary
- versioned Setup/Admin-only Risk configuration with deliberate confirmation and audit
- explicit `RISK_BLOCKED` re-evaluation boundary
- current-runtime broker truth required before fresh risk can be approved

A Risk `PASS` reaches only `RISK_APPROVED`. It is **not** an ExecutionRequest.

**NO LIVE TRADING OR BROKER-WRITE CAPABILITY EXISTS IN TM2/TGT4.**

Module M, real execution, position-management policies, and Exit Monitor remain later roadmap targets.

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
