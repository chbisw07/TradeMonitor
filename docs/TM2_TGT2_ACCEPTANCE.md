# TM2/TGT2 Acceptance — Entry Monitoring and Trade Intent

## Goal

Turn an accepted time-relevant Episode into a deterministic, durable entry-monitoring intent without creating broker execution authority.

## Implemented

- Durable Entry Intent records tied to one Episode.
- Explicit holding intent: `DAY`, `BTST`, `STBT`, `POS`.
- Separate trade horizon and F&O contract expiry.
- Initial asset scope: `EQUITY`, `INDEX`.
- Instrument model: `CASH`, `FUTURE`, `OPTION`; F&O requires expiry, CASH does not.
- Deterministic underlying trigger conditions.
- Optional completed-candle confirmation conditions.
- Underlying invalidation before entry.
- `RETREAT_WAIT` for failed confirmation or unattractive current option economics.
- Explicit rearm from `RETREAT_WAIT` for a fresh evaluation cycle.
- Premium-zone revalidation immediately before `READY_FOR_REVIEW`; no chasing above the permitted zone.
- Horizon/contract-expiry terminal handling.
- Restart-safe persistence and Core trade-context summary.
- Entry monitoring remains separate from Agents, Risk Management, Module M, and broker execution.

## State Meaning

`READY_FOR_REVIEW` means only that deterministic entry checks passed against current facts. It is **not** permission to create risk and is not an `ExecutionRequest`.

A later target must still apply the external Agents validation gate and current Risk Management permission before any risk-creating request may ever reach Module M.

## Safety Boundaries Preserved

- PAPER only.
- No broker write path.
- No order construction/submission.
- No implicit scale-in from repeated observations.
- No Agent implementation inside TM.
- No Risk Management bypass.

## Validation

- Trigger → confirmation waiting.
- Completed-candle confirmation → READY_FOR_REVIEW.
- Failed confirmation → RETREAT_WAIT and explicit rearm.
- Underlying invalidation.
- Horizon expiry.
- Stretched premium → RETREAT_WAIT / do-not-chase.
- All four trade types accepted.
- F&O expiry validation and horizon ≤ expiry.
- CASH future compatibility without expiry.
- Restart while confirming and continuation after restart.
- Full regression suite: **52 passed**.

## Deferred to TM2/TGT3+

- External Agents validation and disagreement escalation.
- Risk Management entry gate.
- User approval semantics associated with Agent disagreement.
- ExecutionRequest and Module M deployment.
- Live broker writes.
