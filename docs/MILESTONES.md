# Milestones

The canonical roadmap is maintained in:

- `TRADEMONITOR_ROADMAP.md`
- `TradeMonitor_TM_Roadmap.docx`

The previous TM0 placeholder milestone list is superseded by the four-milestone roadmap.

## Current Development Position

**TM1 — Core Foundation: COMPLETE / FROZEN**

- TGT1 — Core TM Manager and Runtime Contexts
- TGT2 — Broker Truth and Position Reconciliation
- TGT3 — Health, Fault Containment and Control Room
- TGT4 — PAPER Runtime, Recovery and Replay Validation

**TM2 — Trade Intake + Entry Decision: COMPLETE**

- TGT1 — Trade Intake, Source Identity, Outcome and Episode
- TGT2 — Entry Monitoring and Trade Intent
- TGT3 — External Agents Validation Gate
- TGT4 — Risk Management Entry Gate

**TM3 — Position Management + Exit: COMPLETE / FROZEN-CANDIDATE**

- TGT1 — Position Manager and Adoption: **COMPLETE**
- TGT2 — Deterministic Management Rules: **COMPLETE**
- TGT3 — Exit Monitor and Position Evolution: **COMPLETE**
- TGT4 — Exit Agents and Escalation: **COMPLETE IN THIS WORKING TREE**

TM3/TGT4 adds the independent external Agents gate for strategic/ambiguous exits, User escalation on disagreement/unavailability, automatic bypass for protective/deterministic exits, and restart-safe exit-review history. See `TM3_TGT4_ACCEPTANCE.md`.

**Next:** TM4/TGT1 — Module M and Broker Deployment.

## TM4/TGT1 — Module M and Broker Deployment — COMPLETE

Implemented durable Entry/Exit ExecutionRequests, current-RM entry authorization, isolated Module M deployment, instrument resolution, idempotent submission, broker acknowledgement/partial-fill/fill/reject/cancel/uncertain reconciliation, restart-safe execution persistence, and simulation-only execution gating. Real broker writes remain disabled until later TM4 targets.

## TM4/TGT2 — Execution Simulation, Replay and Failure Injection — COMPLETE

- Dedicated deterministic execution simulator.
- Crash/ack-loss, disconnect, delayed visibility, reconciliation outage, partial fill, rejection and stale-data tests.
- Concurrent deployment/exit-trigger validation.
- End-to-end deterministic replay convergence.
- Real broker writes remain disabled.

## TM4/TGT3 — SEMI_AUTO Controlled Forward Test — CODE READY / LIVE ACCEPTANCE PENDING

- Added explicit per-request User approval gate for real broker deployment.
- PAPER remains default; SEMI_AUTO must be deliberately armed; AUTO remains unavailable.
- Added optional Zerodha reference adapter and controlled operator CLI.
- Fresh unchanged broker reads no longer invalidate RM solely due to a new observation timestamp; a stable risk-state token binds material account facts.
- Operational completion requires a tiny reviewed real-broker forward test.

**Next after live acceptance:** TM4/TGT4 — AUTO Readiness.
