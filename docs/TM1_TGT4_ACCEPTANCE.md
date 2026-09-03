# TM1 / TGT4 Acceptance — PAPER Runtime, Recovery & Replay Validation

## Scope Implemented

TM1/TGT4 closes the TM1 Core Foundation milestone by proving that the PAPER-only runtime can recover, reconcile, contain failures, and replay already-seen facts/events without creating duplicate business side effects.

### Recovery and restart

- Durable contexts survive an ungraceful process loss; a clean `stop()` is not required for already-persisted context mutations to be recoverable.
- Broker truth is re-read after restart and reconciles the restored position state.
- Broker changes that occurred while TM was offline replace stale persisted position facts after a newer coherent broker snapshot is accepted.
- The `MANAGED` / `UNMANAGED` boundary survives restart and reconciliation.

### Freshness and replay semantics

- Broker observations are ordered by their broker-observed timestamp.
- A snapshot older than the last accepted broker observation is classified `STALE` and cannot overwrite newer broker truth.
- An exact-timestamp observation already accepted is classified `REPLAY` and is ignored for business-state mutation.
- Ignored broker observations are still auditable through `BROKER_SNAPSHOT_IGNORED` events.
- Exact duplicate domain events use `event_id` as their idempotency key: they are persisted and published at most once.
- Runtime business-state fingerprints are available for replay validation without treating audit timestamps/context-version increments as business-state changes.

### Failure and recovery behavior

- Repeated identical broker outages do not spam the operator Attention queue.
- When broker reconciliation later succeeds, broker health returns to `HEALTHY` and the corresponding open reconciliation Attention item is resolved.
- A stale context can degrade its owning domain without collapsing the Core or unrelated peer domains.
- Existing TGT3 vertical/horizontal fault-containment behavior remains intact.

### PAPER safety boundary

- Broker API surface remains read-only.
- No order placement, modification, cancellation, exit, or execution method exists on the TM1 Broker contract.
- No live execution capability exists.
- `UNMANAGED` positions remain read-only until a later explicit adoption workflow.

## Validation

The complete test suite now contains **30 passing tests**.

TGT4-specific replay/recovery scenarios cover:

- exact duplicate event replay
- stale/out-of-order broker snapshot rejection
- exact broker snapshot replay
- ungraceful restart with persisted context
- broker truth changing while TM is offline
- degraded broker → healthy recovery
- Attention de-duplication during repeated outage
- stale Market domain isolation
- `UNMANAGED` boundary persistence across restart
- zero broker-write surface

All TM1/TGT1–TGT3 tests remain passing.

## TM1 Exit Criterion — Met

> TradeMonitor can start, recover, understand broker reality, maintain coherent contexts, show `MANAGED` / `UNMANAGED` positions, contain domain failures, tolerate replay/stale observations, and operate safely in PAPER mode. It still cannot place live broker orders.

## Explicitly Deferred to TM2+

- trade intake / `src_id` / Outcome / Episode semantics
- entry trigger and confirmation logic
- Agent service integration
- real Risk Management policies and Admin configuration
- adoption workflow and position-management policies
- Exit Monitor
- Module M broker deployment
- SEMI_AUTO / AUTO execution
