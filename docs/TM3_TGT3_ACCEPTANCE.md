# TM3/TGT3 Acceptance — Exit Monitor and Position Evolution

## Scope completed

- Durable Exit Monitor and Exit Proposal model.
- Protective, deterministic and strategic exit classification.
- Native partial-exit intent: `EXIT_ALL`, `EXIT_QTY`, `EXIT_PERCENT`.
- Duplicate/conflicting exit suppression and full-exit ownership of the exit path.
- Deterministic management-rule signals automatically feed the Exit Monitor.
- Horizon triggers become strategic exit-review proposals.
- DAY end-of-day protection creates a deterministic exit proposal at/after the configured boundary.
- Deliberate managed-position trade-type/horizon conversion.
- Broker truth closes positions and satisfies pending exit proposals.
- Restart-safe persistence of exit proposals.
- Hard `MANAGED / UNMANAGED` boundary preserved.
- No Module M, ExecutionRequest, or broker-write capability.

## Validation

- `pytest`: **91 passed**
- `python -m compileall src`: PASS
- Existing TM1/TM2/TM3-TGT1/TGT2 regression suite remains green.

## Explicitly deferred

- Exit Agents validation and User escalation: TM3/TGT4.
- Real execution deployment / Module M: TM4.
- Broker writes: TM4 only.
