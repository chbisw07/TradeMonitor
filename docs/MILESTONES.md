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

Current implementation target:

- **TM2 / TGT1 — Trade Intake, Source Identity, Outcome and Episode — COMPLETE IN THIS WORKING TREE**

TM2/TGT1 adds durable source observations, broad Outcome identity, time-relevant Episodes, temporal/contract-context reconciliation, de-duplication, existing-exposure awareness, and a bounded external ambiguity-resolution port. See `TM2_TGT1_ACCEPTANCE.md`.

Next roadmap target after acceptance/freeze:

- **TM2 / TGT2 — Entry Monitoring and Trade Intent**
