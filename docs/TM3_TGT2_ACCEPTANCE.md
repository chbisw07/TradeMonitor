# TM3/TGT2 Acceptance — Deterministic Management Rules

## Scope completed

TM3/TGT2 introduces the deterministic managed-position rule engine while preserving the hard `MANAGED / UNMANAGED` boundary and PAPER-only safety posture.

Implemented rule families:

- hard stop-loss (`HARD_SL`)
- take-profit (`TAKE_PROFIT`)
- trailing stop-loss (`TRAILING_SL`)
- profit lock (`PROFIT_LOCK`)
- underlying/spot condition (`SPOT_CONDITION`)
- premium condition (`PREMIUM_CONDITION`)
- P&L condition (`PNL_CONDITION`)
- time exit (`TIME_EXIT`)
- trade horizon (`HORIZON`)
- underlying invalidation (`UNDERLYING_INVALIDATION`)

The engine supports both long and short trailing-stop directionality, stateful arming/ratcheting, explicit rule cancellation, named policy installation, durable runtime state, restart recovery, and auditable rule lifecycle events.

## Architectural boundaries preserved

- Rules can be attached only to open `MANAGED` positions with a management profile.
- `UNMANAGED` positions remain a hard read-only boundary.
- Rule evaluation emits deterministic management signals only.
- A triggered rule does **not** create an `ExecutionRequest` and does not call Module M.
- Exit proposal/concurrency semantics remain TM3/TGT3 scope.
- No broker-write or live-trading capability exists.
- Broker truth remains authoritative for actual position existence, quantity, average price, and state.

## Persistence / recovery

Management rules and their runtime state are persisted in SQLite. Stateful trailing/profit-lock rules survive restart without losing their armed/watermark state.

## Validation

- full test suite: **84 passed**
- source compilation: PASS
- no broker-write API introduced

## Exit criterion

TM can deterministically monitor open `MANAGED` PAPER positions using explicit management rules/policies and produce auditable exit-review signals. TM3/TGT3 will own conversion of those signals into coherent exit proposals and position evolution.
