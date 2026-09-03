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

Current implementation position:

- **TM2 / TGT1 — Trade Intake, Source Identity, Outcome and Episode — COMPLETE**
- **TM2 / TGT2 — Entry Monitoring and Trade Intent — COMPLETE IN THIS WORKING TREE**

TM2/TGT2 adds durable entry intents, trigger/confirmation monitoring, RETREAT_WAIT/rearm, invalidation, current-market premium revalidation, DAY/BTST/STBT/POS intent, and separate horizon/F&O expiry semantics. See `TM2_TGT2_ACCEPTANCE.md`.

Next roadmap target after acceptance/freeze:

- **TM2 / TGT3 — External Agents Validation Gate**
