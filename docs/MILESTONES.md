# Milestones

The canonical roadmap is maintained in:

- `TRADEMONITOR_ROADMAP.md`
- `TradeMonitor_TM_Roadmap.docx`

The previous TM0 placeholder milestone list is superseded by the four-milestone roadmap.

## Current Development Position

**TM1 — Core Foundation**

Completed and frozen: **TGT1 — Core TM Manager and Runtime Contexts**

Current target: **TGT2 — Broker Truth and Position Reconciliation**

TM1/TGT2 establishes a read-only broker snapshot contract, durable broker-truth reconciliation, unified `MANAGED` / `UNMANAGED` positions, persistence across restart, and explicit enforcement of the unmanaged read-only boundary. It contains **no live broker write capability**.
