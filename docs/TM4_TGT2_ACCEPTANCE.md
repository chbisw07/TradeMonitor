# TM4/TGT2 Acceptance — Execution Simulation, Replay and Failure Injection

## Purpose

TM4/TGT2 does not add live trading. It stress-tests the TM4/TGT1 execution boundary under ambiguity, restart, delayed broker truth, partial execution, stale data and concurrent triggers before any real broker adapter is introduced.

## Implemented

- Added `SimulatedExecutionBroker`, a deterministic PAPER execution simulator separate from the minimal TGT1 mock.
- Simulator supports:
  - broker accepts order and acknowledgement is lost (`ACCEPT_THEN_TIMEOUT`),
  - disconnect before broker acceptance,
  - delayed client-order visibility,
  - temporary reconciliation disconnects,
  - partial-fill / fill / reject truth transitions,
  - deterministic broker-side client-order idempotency.
- Module M reconciliation now contains broker-fetch failures as `UNCERTAIN` rather than crashing or blind-resubmitting.
- Stale broker-order snapshots are ignored and cannot roll a newer execution state backward.
- Explicitly stale/unavailable Market context blocks price-dependent creation/deployment of new exposure.
- Restart/recovery tests prove that an order accepted before acknowledgement loss is recovered through broker truth without resubmission.
- Delayed broker visibility converges from `UNCERTAIN` to current broker truth without duplicate exposure.
- Partial-fill runtime state survives restart and later converges to filled broker truth.
- Rejected orders remain terminal under replay.
- Concurrent duplicate deploy calls submit exactly once.
- Concurrent full-exit triggers coalesce before execution rather than creating competing full-exit paths.
- End-to-end replay of the same deterministic execution session converges to the same business state.

## Safety Acceptance

The following invariants remain enforced:

> Nothing creating risk reaches Module M without current Risk Management permission.

> Submission ambiguity is not permission to retry blindly.

> Missing or delayed broker acknowledgement is `UNCERTAIN`, not `FAILED`.

> New exposure is not deployed when Market context is explicitly stale/unavailable.

> Older broker-order observations cannot overwrite newer broker truth already accepted by TM.

> Real broker writes remain disabled in TM4/TGT2.

## Failure / Replay Scenarios Validated

- crash/restart after broker accepted an order but before TM received acknowledgement,
- disconnect before broker acceptance,
- restart with durable pending/uncertain order state,
- delayed broker reconciliation / eventual visibility,
- temporary broker reconciliation disconnect,
- partial fill followed by restart and final fill,
- rejection and terminal replay,
- stale Market context,
- stale broker-order snapshot,
- concurrent duplicate deployment,
- concurrent full-exit triggers,
- deterministic end-to-end session replay.

## Explicitly Deferred

- No real broker execution adapter.
- No SEMI_AUTO real-order workflow.
- No AUTO readiness decision.

Those belong to TM4/TGT3 and TM4/TGT4 respectively.
