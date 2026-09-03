# TM2/TGT3 Acceptance — External Agents Validation Gate

## Goal

Integrate the external Agents validation boundary for entry decisions without giving Agents state ownership, Risk authority, execution authority, or broker access.

## Implemented

- Explicit `AgentGateway` port for a separate external Agents service.
- Bounded `AgentEntryReviewPacket` built from an entry intent only after `READY_FOR_REVIEW`.
- Mandatory Agent verdict: `APPROVE`, `REJECT`, or `RETREAT_WAIT`.
- Optional suggestion retained and logged independently from the mandatory verdict.
- Agent `APPROVE` advances only to `READY_FOR_RISK`; it does not create an execution request.
- Agent `REJECT` / `RETREAT_WAIT` escalates to the User.
- User then records exactly one of `APPROVE`, `REJECT`, or `RETREAT_WAIT`.
- User `APPROVE` advances only to `READY_FOR_RISK`; Risk Management remains the next authority gate.
- User `REJECT` terminates the entry intent.
- User `RETREAT_WAIT` returns the intent to the existing retreat/wait lifecycle.
- Agent unavailability/protocol failure escalates to User and never implies approval.
- Durable Agent review records and restart-safe Attention items.
- Review/Risk handoff states cannot be silently reversed by later market ticks.

## Explicitly Not Implemented

- No Agents reasoning implementation inside TradeMonitor.
- No HTTP/RPC transport to an actual Agents deployment yet; only the TM-side port/contract exists.
- No Risk Management entry gate (TM2/TGT4).
- No ExecutionRequest.
- No Module M deployment.
- No broker writes or live trading.

## Validation

- Full test suite: **60 passed**.
- `python -m compileall src`: PASS.
- Agent approve, disagreement, User escalation, Agent failure, persistence/restart, and state-ownership boundaries are covered.

## Acceptance Statement

TM2/TGT3 is accepted when the local repository also reports all tests passing and the runtime remains PAPER-only. The next roadmap target is **TM2/TGT4 — Risk Management Entry Gate**.
