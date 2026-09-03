# TM3 / TGT1 Acceptance — Position Manager and Adoption

## Purpose

TM3/TGT1 establishes the unified Position domain and the explicit boundary by which an externally created broker position can move from `UNMANAGED` to `MANAGED`.

## Implemented

- One canonical broker-reconciled Position universe.
- `management_status = MANAGED | UNMANAGED` remains orthogonal to broker state.
- Broker-discovered positions remain `UNMANAGED / BROKER_EXTERNAL` by default.
- `UNMANAGED` remains a hard read-only boundary for TradeMonitor management.
- Explicit adoption workflow crosses `UNMANAGED -> MANAGED`; there is no implicit adoption.
- Adoption performs **no broker write** and does not change broker quantity, average price, instrument identity, or state.
- Current-runtime broker reconciliation is required before adoption so the decision is based on current broker truth rather than persisted last-known state.
- Adoption requires sufficient management context:
  - asset class,
  - instrument type,
  - trade type (`DAY / BTST / STBT / POS`),
  - horizon,
  - F&O expiry for FUTURE/OPTION,
  - initiating user/authority identity and an explicit reason.
- Adopted broker positions change provenance from `BROKER_EXTERNAL` to `BROKER_ADOPTED` while retaining the same canonical position ID.
- Management intent is persisted separately from broker-truth fields in a Position Management Profile.
- The same Position Management Profile shape is reserved for future TM-native positions, allowing native and adopted positions to converge on the same downstream management engine.
- Adoption is durably logged as `POSITION_ADOPTED`.
- Adoption state/profile survive restart and later broker reconciliation.
- Broker truth continues to win after adoption; changes in broker quantity/average/state update the Position while preserving management authority/profile.
- Closed positions cannot be adopted; already-managed positions cannot be adopted again.

## Intentionally deferred

TM3/TGT1 does **not** implement:

- SL / TP / TSL,
- profit locks or P&L management rules,
- exit policy execution,
- strategic Exit Monitor behavior,
- partial exits,
- exit Agents integration,
- Module M execution requests,
- real broker write/order capability.

These belong to later TM3/TM4 targets.

## Safety invariants validated

1. Broker reality remains factual truth.
2. An `UNMANAGED` position is read-only until explicit adoption.
3. Adoption changes TM management authority only; it never changes broker reality.
4. No position can be adopted from stale persisted broker state without current-runtime reconciliation.
5. F&O adoption cannot omit contract expiry.
6. Adoption is explicit and auditable.
7. After adoption, broker reconciliation still overrides stale internal quantity/state while preserving the `MANAGED` status and management profile.
8. No broker-write/live-trading capability was added.

## Validation

- Full test suite: **75 passed**.
- New unit coverage: adoption boundary, required management information, invalid adoption states.
- New integration coverage: current-runtime reconciliation requirement, restart persistence, and post-adoption broker-truth reconciliation.
- `python -m compileall src` passes.

## TGT1 exit criterion

> An external broker position can remain read-only as `UNMANAGED` or be explicitly adopted as `MANAGED`; after adoption it has durable management context and is ready to use the same future management machinery as a TM-native position, while broker truth remains authoritative.
