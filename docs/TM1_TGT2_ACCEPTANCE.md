# TM1/TGT2 Acceptance — Broker Truth and Position Reconciliation

## Target

Establish a read-only broker-truth boundary and a durable, unified Position context without introducing any broker write capability.

## Implemented

- Read-only `Broker` adapter contract returning coherent account snapshots.
- Deterministic `MockBroker` for PAPER/integration testing.
- Broker snapshot models for positions and funds plus order/fill counts when a broker supports them.
- Durable canonical Position records in SQLite.
- Unified `MANAGED` / `UNMANAGED` management status.
- New broker-discovered positions default to `UNMANAGED` / `BROKER_EXTERNAL`.
- Broker quantity/state/average price wins during reconciliation.
- Existing management status and provenance are preserved during reconciliation.
- Previously-open positions missing from a coherent broker snapshot are closed internally because broker reality is truth.
- `UNMANAGED` boundary is explicitly enforced as read-only until a later adoption workflow.
- Broker and Position runtime contexts are refreshed after reconciliation.
- Structured events for discovery/change/closure/reconciliation.
- Position state survives restart and is reconciled again against current broker truth.
- Console shows unified positions and their `MANAGED` / `UNMANAGED` status.

## Safety Boundary

TM1/TGT2 remains **PAPER/read-only with respect to the broker**.

The broker interface contains no order placement, modification, cancellation, exit, hedge, or adoption operation. This target cannot create or alter broker exposure.

`UNMANAGED` positions may be observed and later counted by Risk Management, but they cannot be operated upon until explicitly adopted in a later milestone.

## Validation

Validation result: **15 tests passed**.

Acceptance tests cover:

- new broker position => `UNMANAGED`;
- hard read-only boundary;
- broker quantity/state overrides stale internal assumptions;
- preservation of `MANAGED` status/provenance during reconciliation;
- broker-observed closure;
- persistence/restart;
- broker context/funds summary;
- absence of broker write methods.

## Explicitly Deferred

- Real Zerodha/AngelOne/Dhan broker adapter and authentication.
- Explicit adoption workflow (`UNMANAGED -> MANAGED`).
- Risk Management calculations using position exposure.
- Entry/exit decision logic.
- SL/TP/TSL and management policies.
- Agents service.
- Module M and all live execution operations.
