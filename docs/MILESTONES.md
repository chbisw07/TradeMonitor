# Milestones

The canonical roadmap is maintained in:

- `TRADEMONITOR_ROADMAP.md`
- `TradeMonitor_TM_Roadmap.docx`

The previous TM0 placeholder milestone list is superseded by the four-milestone roadmap.

## Current Development Position

**TM1 — Core Foundation**

Completed and frozen:

- **TGT1 — Core TM Manager and Runtime Contexts**
- **TGT2 — Broker Truth and Position Reconciliation**
- **TGT3 — Health, Fault Containment and Control Room**
- **TGT4 — PAPER Runtime, Recovery and Replay Validation**

TM1 is complete in this working tree. TGT4 validates restart/recovery, stale and replayed broker observations, duplicate-event tolerance, broker degraded→healthy recovery, persistent auditability, and the hard PAPER/read-only safety boundary.

Next roadmap milestone after TM1 acceptance/freeze:

- **TM2 / TGT1 — Trade Intake, Source Identity, Outcome and Episode**
