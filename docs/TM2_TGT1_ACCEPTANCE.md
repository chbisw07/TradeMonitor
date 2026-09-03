# TM2 / TGT1 Acceptance — Trade Intake, Source Identity, Outcome and Episode

## Status

Implemented and validated on top of the frozen TM1/TGT4 foundation.

## Implemented

- Immutable source observations with explicit `src_id`, source, timestamp, normalized intent and raw provenance.
- Broad Outcome identity separated from time/contract-specific Episode identity.
- Time-relevant Episode reconciliation with a small deterministic relevance policy.
- Same source may legitimately produce different Outcomes.
- Different sources may converge on the same Outcome/Episode without duplicate operational paths.
- Exact observation replay is idempotent.
- Material contract/context change can create a new Episode of the same Outcome.
- High-ambiguity Episode reconciliation has an explicit external-service port; TM core contains no Agents implementation.
- Existing broker-confirmed exposure is detected and marked as rediscovery; it never creates scale-in permission.
- Intake state is durable and survives restart.
- Core `trade` context receives only summarized intake counts; Intake remains the domain owner.
- No entry trigger logic, Agent validation workflow, RM entry gate, Module M, or broker writes were introduced.

## Architectural invariants preserved

- Broker reality remains truth for positions.
- `UNMANAGED` remains a hard read-only boundary.
- Repeated signals never imply add/scale-in.
- Agents remain a separate external service and may only be consulted through an explicit bounded interface.
- Nothing in TGT1 can create broker risk.

## Acceptance statement

> TM can distinguish duplicates, updates, new Episodes, distinct Outcomes, and existing-exposure rediscovery without creating duplicate operational trade paths.
