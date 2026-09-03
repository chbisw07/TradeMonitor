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

Current implementation target completed in this working tree:

- **TGT3 — Health, Fault Containment and Control Room**

TM1/TGT3 adds domain health reporting, vertical nearest-owner fault containment/escalation, horizontal peer-domain isolation, capability-specific degradation, a durable Attention queue, and a unified control-room view. It preserves the read-only broker boundary and contains **no live broker write capability**.

Next roadmap target after TGT3 acceptance/freeze:

- **TGT4 — PAPER Runtime, Recovery and Replay Validation**
