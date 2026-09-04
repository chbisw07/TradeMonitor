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
