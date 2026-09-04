# TradeMonitor

**Current milestone:** TM4/TGT2 — Execution Simulation, Replay and Failure Injection

TradeMonitor is being developed as a professional trade-monitoring, risk-governance, position-management, and execution system for Indian markets.

The canonical design references are kept under `docs/`:

- `TradeMonitor_TM0_Architecture_Thesis.docx`
- `TRADEMONITOR_ROADMAP.md`
- `TradeMonitor_TM_Roadmap.docx`

## Current Status

**TM4 / TGT1 — Module M and Broker Deployment — COMPLETE**

TM1 and TM2 are complete. TM3 now includes deterministic managed-position rules:

- unified `MANAGED / UNMANAGED` Position universe and explicit adoption boundary
- deterministic SL / TP / TSL, profit-lock, spot/premium/P&L, time/horizon, and invalidation rules
- named rule-policy installation and explicit rule cancellation
- stateful trailing/profit-lock rules with durable arming/ratcheting state
- management-rule state survives restart
- triggered rules emit auditable `EXIT_REVIEW` signals only; they do not create ExecutionRequests
- broker truth remains authoritative and `UNMANAGED` positions remain read-only

**NO REAL/LIVE BROKER-WRITE CAPABILITY EXISTS IN TM4/TGT2. Module M remains enabled only for simulation adapters in PAPER mode.**

TM3/TGT4 now provides durable PAPER-only exit proposals, partial-exit shapes, duplicate/conflicting exit suppression, DAY end-of-day protection, deliberate position holding-intent conversion, and broker-truth closure convergence. Module M and real execution remain TM4 scope.




## Google Sheet PAPER intake trial

A read-only optional Google Sheet feeder is available for exercising real `Top Picks` candidates through the canonical TM Intake boundary while keeping execution simulation-only.

Install optional support:

```bash
pip install -e '.[google]'
```

Configure `.env`, then validate mapping first:

```bash
python scripts/feed_google_top_picks.py --dry-run --limit 5
```

If the mapping is correct, persist the observations into TM:

```bash
python scripts/feed_google_top_picks.py --limit 5
python scripts/run_dev.py
```

See `docs/GOOGLE_SHEET_FEEDER.md`. Google-specific field names remain entirely outside TM core.


## TM4/TGT2 — Execution Failure / Replay Validation

TM4/TGT2 stress-tests Module M rather than adding live trading. A dedicated simulation broker now reproduces acknowledgement loss after broker acceptance, disconnect-before-accept, delayed order visibility, reconciliation outages, partial fills and rejection. Restart/replay tests prove idempotent convergence to broker truth. Explicitly stale Market context blocks creation/deployment of new exposure. Real broker writes remain disabled.

See `docs/TM4_TGT2_ACCEPTANCE.md`.

## TM4/TGT1 — Module M

TM4/TGT1 introduces the execution-deployment boundary without enabling real broker writes:

- durable, idempotent `ExecutionRequest` handoffs for both ENTRY and EXIT
- entry handoff requires a current matching RM `PASS`; broker truth or Risk-profile changes invalidate stale permission
- Module M resolves instruments, submits normalized orders, tracks acknowledgement/partial fill/fill/reject/cancel/uncertain states, and reconciles to broker order truth
- repeat/restart deployment of the same authorized intent cannot blindly create a duplicate order
- submission uncertainty is preserved as `UNCERTAIN`; missing acknowledgement is never interpreted as failure
- the original read-only `Broker` interface remains separate from the opt-in `ExecutionBroker` interface
- only simulation execution brokers are permitted in this target; real broker adapters remain TM4/TGT3 scope

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


## Google Top Picks PAPER integration

After validating Google Sheet intake, eligible Top Picks can be admitted to the generic Entry Monitor without exposing workbook schema to TM core:

```bash
python scripts/feed_google_top_picks.py --dry-run --limit 5 --create-entry-intents
python scripts/feed_google_top_picks.py --limit 5 --create-entry-intents
```

This is still PAPER-only. It creates/recovers EntryIntents but does not provide a market-data loop or live broker writes.
