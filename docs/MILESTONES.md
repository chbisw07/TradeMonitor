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

**TM3 — Position Management + Exit: IN PROGRESS**

- TGT1 — Position Manager and Adoption: **COMPLETE**
- TGT2 — Deterministic Management Rules: **COMPLETE**
- TGT3 — Exit Monitor and Position Evolution: **COMPLETE IN THIS WORKING TREE**
- Next: TGT4 — Exit Agents and Escalation

TM3/TGT3 converts triggered management signals and explicit strategic requests into durable PAPER-only Exit Proposals, supports partial-exit intent, suppresses conflicting exit paths, protects DAY end-of-day behavior, supports deliberate holding-intent conversion, and converges to broker truth on closure. See `TM3_TGT3_ACCEPTANCE.md`.
