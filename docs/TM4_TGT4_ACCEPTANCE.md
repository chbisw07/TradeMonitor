# TM4/TGT4 — AUTO Readiness

## Purpose

TM4/TGT4 turns AUTO from a mode name into an evidence-gated operational capability. AUTO is **not** granted merely because TM4/TGT3 code exists or because Zerodha connectivity works.

## Implemented

- Durable AUTO-readiness evidence stored in the execution context.
- Deterministic readiness assessment against the TM4 roadmap requirements.
- Evidence must demonstrate repeated SEMI_AUTO operation (minimum 3 reviewed sessions and 3 real executions), zero unresolved reconciliation defects, zero duplicate-execution defects, and validated restart/recovery, RM, Position/Exit, Agent degradation, and operating safeguards.
- Recording changed evidence revokes a prior AUTO-enable decision automatically.
- Explicit User decision requires the exact confirmation `ENABLE AUTO`.
- AUTO runtime startup requires all of:
  1. persisted readiness assessment = READY,
  2. explicit persisted AUTO-enable decision bound to the current evidence digest,
  3. `TM_ALLOW_AUTO_EXECUTION=true`,
  4. `TM_ALLOW_REAL_BROKER_WRITES=true`.
- AUTO broker deployment still reuses Module M and the existing current broker/RM authorization checks. It removes the *per-request SEMI_AUTO approval* only after the above AUTO gate has been satisfied.
- PAPER remains the default.
- SEMI_AUTO behavior remains unchanged.
- Added `scripts/auto_readiness.py` for review/evidence/decision operations. This utility has no broker write capability.
- Console/control-room now displays AUTO readiness, decision state, and blockers.

## Important operational status

The code can evaluate AUTO readiness, but the current Zerodha read-only validation by itself is **not sufficient evidence for AUTO**. Read-only connection/reconciliation does not count as a real SEMI_AUTO execution. Therefore a normal existing TradeMonitor database should initially show AUTO as `NOT READY`.

Do not fabricate evidence merely to make the gate green.

## Evidence JSON shape

```json
{
  "semi_auto_sessions": 3,
  "semi_auto_real_executions": 3,
  "unresolved_reconciliation_defects": 0,
  "duplicate_execution_defects": 0,
  "restart_recovery_validated": true,
  "risk_management_validated": true,
  "position_exit_validated": true,
  "agent_degradation_validated": true,
  "operating_safeguards_validated": true,
  "note": "reviewed evidence pack"
}
```

Show current state:

```bash
python scripts/auto_readiness.py
```

Record a reviewed evidence file:

```bash
python scripts/auto_readiness.py --record auto_evidence.json --recorded-by USER
```

Only after the report says `READY`, record the explicit decision:

```bash
python scripts/auto_readiness.py \
  --enable \
  --recorded-by USER \
  --reason "reviewed TM4/TGT4 evidence" \
  --confirmation "ENABLE AUTO"
```

Even then, AUTO cannot start unless the two environment arms are also explicitly enabled.

## Acceptance

Automated acceptance requires the entire historical suite plus TGT4 tests to pass, compileall to pass, and the default runtime to remain PAPER-safe.
