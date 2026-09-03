# TM1 / TGT3 Acceptance — Health, Fault Containment & Control Room

## Scope Implemented

TM1/TGT3 implements the roadmap's health/fault architecture and control-room baseline while preserving the PAPER-only, read-only broker boundary.

### Health and fault model

- Horizontal peer domains can report summarized health to the Core TM Manager.
- Health states support `UNKNOWN`, `HEALTHY`, `DEGRADED`, `UNAVAILABLE`, and `RECOVERING`.
- Health reports carry business impact and capability-specific availability rather than only raw exception text.
- Vertical faults are represented as child/component → immediate competent owner; locally resolved faults are contained there, while unresolved faults can be escalated to the next parent.
- A failing peer domain does not automatically collapse unrelated domains.
- Broker reconciliation failure marks broker truth unavailable/stale, raises operator attention, and does not imply that Core itself failed.

### Control room

- Unified control-room rendering includes:
  - system/runtime/PAPER mode
  - domain health and capability impact
  - unified Positions pane using `MANAGED` / `UNMANAGED`
  - durable Attention queue
- Attention items are persistent across restart and explicitly resolvable.

### Safety retained

- Broker access remains read-only.
- No broker order submission/modification/cancellation exists.
- No live execution capability exists.
- `UNMANAGED` positions remain read-only.
- Failure never silently becomes greater authority or capability.
- Only PAPER mode is operational in TM1/TGT3.

## Validation

Acceptance is demonstrated by the unit/integration tests covering:

- horizontal health containment
- vertical local fault containment and escalation
- durable Attention queue
- control-room rendering
- broker degraded-mode behavior
- all prior TM1/TGT1 and TM1/TGT2 reconciliation/restart/safety tests

## Explicitly Deferred to TGT4+

- replay/failure-injection harness breadth
- timed recovery/backoff orchestration
- real broker connectivity
- entry/exit trading logic
- real Risk Management policies
- Agent service integration
- Module M broker writes
- SEMI_AUTO / AUTO execution
