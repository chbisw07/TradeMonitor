# TM2/TGT4 Acceptance — Risk Management Entry Gate

## Scope implemented

TM2/TGT4 implements the authoritative pre-trade Risk Management gate while preserving PAPER-only operation and all TM0 architectural boundaries.

Implemented behavior:

- `READY_FOR_RISK` entry intents can be evaluated by RM.
- Deterministic Risk verdict is exactly `PASS` or `BLOCK`.
- A `PASS` produces `RISK_APPROVED`; a `BLOCK` produces `RISK_BLOCKED`.
- Broker truth must be reconciled in the current TM runtime before new exposure can be approved.
- Account/portfolio metrics include all open broker positions, both `MANAGED` and `UNMANAGED`.
- `UNMANAGED` positions remain read-only; RM only counts their exposure.
- Versioned Risk Profiles support optional limits for maximum position value, maximum trade loss, maximum open positions, and maximum total exposure.
- No business thresholds were invented in the bootstrap profile.
- Setup/Admin risk changes use a deliberate two-step `propose -> CONFIRM` workflow with an explicit reason and permanent audit event.
- Profile changes do not automatically revive blocked trades.
- Explicit Risk re-evaluation is required to return a blocked trade to `READY_FOR_RISK`.
- Every Risk block is durably logged and surfaced in the Attention queue.
- Risk decisions/profile changes survive restart.
- No ExecutionRequest, Module M deployment, or broker-write path is added.

## Acceptance validation

- Full automated suite: **70 tests passed**.
- `python -m compileall src`: PASS.
- Existing TM1/TM2 regression behavior remains green.
- Risk-block persistence/restart behavior validated.
- Persisted broker truth after restart is deliberately insufficient until current-runtime reconciliation occurs.
- `UNMANAGED` portfolio exposure participation validated without violating the management boundary.

## TM2 completion statement

With TGT1–TGT4 complete, TM2 can ingest and reconcile opportunities, monitor deterministic entry conditions, obtain independent external Agent review, escalate Agent disagreement to the User, and apply the highest-authority Risk Management gate to determine whether proposed new exposure is permitted.

TradeMonitor remains **PAPER-only with zero broker-write capability**.
