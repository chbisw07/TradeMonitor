# TM4/TGT1 Acceptance — Module M and Broker Deployment

## Purpose

TM4/TGT1 introduces the execution-deployment boundary after TM1–TM3 proved reality, entry governance, Risk Management, and position/exit management. It does **not** enable real broker trading.

## Implemented

- Durable `ExecutionRequest` model for both ENTRY and EXIT.
- Entry request construction is possible only from a `RISK_APPROVED` intent with the latest matching RM `PASS`.
- Entry authorization becomes stale if the active Risk profile changes or broker truth has changed since the RM decision.
- Exit requests are built only from `APPROVED` exit proposals on open `MANAGED` broker-confirmed positions.
- Module M is deployment-only: instrument resolution, normalized order construction, submission, acknowledgement tracking, reconciliation, and explicit cancellation.
- Durable order lifecycle includes READY, SUBMITTING, SUBMITTED, PARTIALLY_FILLED, FILLED, REJECTED, CANCELLED, and UNCERTAIN.
- Idempotency key is persisted before broker submission; repeated/restarted deployment does not blind-submit again.
- Submission exceptions become `UNCERTAIN`; missing acknowledgement is not treated as broker failure.
- Broker order truth is correlated by client/idempotency ID and becomes factual order state.
- The original read-only `Broker` contract remains intact; write capability requires explicit `ExecutionBroker` opt-in.
- TM4/TGT1 permits only simulation execution adapters in PAPER mode. No real broker adapter is supplied.
- Versioned `execution` runtime context added to the Core control room.

## Safety Acceptance

> Nothing creating risk reaches Module M without current Risk Management permission.

Further:

- Agent approval never reaches Module M directly.
- `UNMANAGED` positions cannot produce exit ExecutionRequests.
- One authorization/idempotency key maps to one durable ExecutionRequest.
- Once submission has begun, retry means reconciliation, not automatic resubmission.
- Real broker writes are rejected by the Core in TM4/TGT1.

## Validation

- Full regression suite: 118 tests passing.
- Source compilation: PASS.
- Entry and exit both exercise the same Module M deployment path.
- Restart/idempotency test proves repeated deployment does not resubmit the same broker intent.
- Partial-fill/fill/reject/uncertain order states are reconciled from broker truth.

## Explicitly Deferred

TM4/TGT2 will deepen broker simulation, replay, crash/failure injection, delayed reconciliation, and concurrent execution scenarios.

TM4/TGT3 is the first target intended to introduce a real broker adapter under SEMI_AUTO controls.
