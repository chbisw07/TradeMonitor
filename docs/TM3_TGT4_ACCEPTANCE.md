# TM3/TGT4 Acceptance — Exit Agents and Escalation

## Scope

TM3/TGT4 adds the independent external Agents validation gate to **strategic / ambiguous exit decisions** while preserving the authority and execution boundaries defined in the TM0 thesis.

## Accepted behavior

- The Agents service remains external to TradeMonitor; TM contains only the gateway/contract and orchestration.
- Strategic exit proposals may be sent to Agents as bounded review packets.
- Agents must return exactly one verdict: `APPROVE`, `REJECT`, or `RETREAT_WAIT`.
- Agent suggestions are optional advice only; they do not create rules, modify positions, or invoke execution.
- Agent `APPROVE` marks the strategic exit proposal `APPROVED` for a later TM4 execution stage.
- Agent `REJECT` / `RETREAT_WAIT` escalates to the User, who chooses `APPROVE / REJECT / RETREAT_WAIT`.
- Agent failure or protocol failure never implies approval; it escalates to the User.
- Protective and deterministic exits do **not** wait for Agents. They are approved by their already-authorized policy/risk path.
- A later protective/deterministic full-exit trigger promotes an existing lower-authority strategic full-exit path so safety cannot remain blocked behind Agent/User review.
- Exit review history, Agent suggestions, User decisions, and Attention survive restart.
- `UNMANAGED` remains a hard read-only boundary.
- No `ExecutionRequest`, Module M deployment, or broker write capability exists in TM3/TGT4.

## Validation

- Full automated suite: **101 passed**.
- `python -m compileall src`: PASS.
- Control-room smoke run: PASS.
- PAPER-only / read-only broker boundary preserved.

## TM3 milestone status

With TGT4 complete, **TM3 — Position Management + Exit is complete**. The next milestone is **TM4 — Execution + Production Readiness**.
