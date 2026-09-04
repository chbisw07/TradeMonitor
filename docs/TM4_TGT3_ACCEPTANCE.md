# TM4/TGT3 — SEMI_AUTO Controlled Forward Test

## Purpose

Introduce the first deliberately gated real-broker path without granting TradeMonitor autonomous execution authority.

## Implemented

- `PAPER` remains the default and safest mode.
- `SEMI_AUTO` is the only live-capable mode in TGT3; `AUTO` is refused.
- Real broker writes require **all** of the following:
  1. `TM_EXECUTION_MODE=SEMI_AUTO`
  2. `TM_ALLOW_REAL_BROKER_WRITES=true`
  3. a non-simulation `ExecutionBroker`
  4. current broker truth
  5. current Risk Management permission for ENTRY
  6. an explicit, durable User approval bound to the exact `ExecutionRequest`
  7. approval still within the configured TTL at deployment
- Approval decisions are durable, auditable, and exposed in the execution context.
- `REJECT` never grants execution.
- Live reconciliation/cancellation remain broker-truth driven.
- Added optional Zerodha Kite Connect adapter (`kiteconnect>=5.2.1,<6`).
- Zerodha idempotency uses a deterministic short broker tag derived from TM's full idempotency key, allowing restart-safe lookup.
- Added a deliberately explicit `scripts/zerodha_semi_auto.py` operator utility.
- Broker Risk authorization now binds to a stable **risk-state token** rather than a local observation timestamp alone. A fresh read of unchanged account facts does not invalidate a Risk PASS; a material account-state change does.

## Safety boundaries

- No trade is selected or invented by the SEMI_AUTO utility.
- The utility operates only on an already-existing durable `ExecutionRequest`.
- Module M remains the only broker-deployment owner.
- Nothing creating risk reaches Module M without current RM permission.
- A User approval cannot override RM.
- Every real request still requires an explicit per-request approval; enabling SEMI_AUTO is not blanket execution permission.
- Approval expiry forces a fresh User decision.
- `AUTO` remains out of scope.

## Validation

Automated validation covers PAPER compatibility, live-write gating, explicit approval, rejection, approval expiry, restart persistence, current broker/Risk revalidation, and Zerodha adapter mapping/idempotency behavior.

**Automated suite: 159 tests passing; compileall and PAPER control-room smoke pass.**

**Important:** automated tests make TGT3 *code-ready*. TGT3 is not operationally accepted until a deliberately tiny real-broker forward test is performed and reviewed. Do not enable broad live use merely because the test suite passes.
