# TradeMonitor Development Roadmap

**Status:** Canonical development map  
**Architecture reference:** TradeMonitor TM0 Architecture Thesis  
**Purpose:** Preserve the implementation sequence, milestone boundaries, acceptance gates, and safety progression for TradeMonitor.

---

## 1. Roadmap Philosophy

TradeMonitor will be developed through **four major milestones**. Each milestone contains smaller **TGT** targets that can be implemented, tested, reviewed, and frozen independently.

The milestones are intentionally capability-based:

- **TM1 — Know Reality**
- **TM2 — Decide Entry**
- **TM3 — Manage Position**
- **TM4 — Execute for Real**

This ordering is deliberate. Live broker execution is introduced only after the runtime core, broker reconciliation, entry decision flow, Risk Management, position management, exit logic, and recovery behavior have already been exercised in PAPER mode.

The roadmap follows the TM0 architectural principles:

- Broker reality is factual truth for broker orders, fills, and positions.
- Risk Management is the highest runtime authority inside TM.
- Nothing creating risk reaches Module M without current Risk Management permission.
- The User is the highest normal discretionary authority below Risk Management.
- Module M deploys authorized execution requests; it does not decide whether a trade is good.
- Agents are an external, low-authority advisory/validation service.
- Positions use a unified `MANAGED` / `UNMANAGED` management status.
- `UNMANAGED` broker positions are read-only until explicitly adopted.
- TM remains simple, loosely coupled, responsible, flexible, and capable of degrading by capability.

---

## 2. Milestone Overview

| Milestone | Purpose | Primary Outcome |
|---|---|---|
| **TM1** | Core Foundation | TM understands reality and maintains coherent runtime state |
| **TM2** | Trade Intake + Entry Decision | TM can decide whether a trade should be entered |
| **TM3** | Position Management + Exit | TM can manage a position from entry to closure |
| **TM4** | Execution + Production Readiness | TM can safely deploy approved actions to a real broker |

---

# TM1 — Core Foundation

## Goal

Build the reliable TradeMonitor runtime around the TM0 thesis. TM should be able to start, recover, synchronize its contexts, understand broker reality, and present one coherent operational picture while remaining incapable of live trading.

### TGT1 — Core TM Manager and Runtime Contexts

Build the small coordinating core and the initial context model.

Scope includes:

- Core TM Manager
- event routing / coordination foundation
- runtime contexts for broker, market, trade, position, risk, decision, and health
- persistence foundation
- restart/recovery framework
- structured event/audit logging
- controlled state transitions
- no live execution capability

**Acceptance:** TM can start, initialize its contexts, persist meaningful state, restart, and reconstruct a coherent runtime view.

### TGT2 — Broker Truth and Position Reconciliation

Establish broker reality as factual truth.

Scope includes:

- broker adapter foundation
- read broker positions/orders/fills/funds as supported
- reconcile persisted TM state with broker state
- unified Positions view
- `MANAGED` / `UNMANAGED`
- origin/provenance retained independently from management status
- `UNMANAGED` positions visible and risk-visible but read-only
- no implicit adoption
- basic adoption workflow may be introduced if needed for testing, without full management policies

**Acceptance:** TM accurately reflects broker reality after startup/restart and cannot modify an `UNMANAGED` position.

### TGT3 — Health, Fault Containment, and Control Room

Implement the architectural fault model and professional console baseline.

Scope includes:

- vertical failure handling: closest competent parent handles first, escalates upward when necessary
- horizontal peer domains own and contain failures
- domain health reporting
- `HEALTHY / DEGRADED / UNAVAILABLE / RECOVERING`-style health semantics as appropriate
- capability-specific degradation
- Attention queue
- unified Positions pane
- system/broker/market/RM health panel
- PAPER / SEMI_AUTO / AUTO framework may exist, but only PAPER is actionable

**Acceptance:** Failure of one non-critical domain does not unnecessarily collapse unrelated capabilities, and the operator can see what failed and what TM is doing about it.

### TGT4 — PAPER Runtime, Recovery, and Replay Validation

Exercise the complete TM1 runtime.

Scope includes:

- restart during active state
- broker-state mismatch reconciliation
- stale data handling
- duplicate-event tolerance
- simulated component failure
- crash/recovery scenarios
- persistent logs and auditability
- no broker write operations

**TM1 Exit Criterion**

> TM can start, recover, understand broker reality, maintain coherent contexts, show `MANAGED` / `UNMANAGED` positions, contain domain failures, and operate safely in PAPER mode. It still cannot place live broker orders.

---

# TM2 — Trade Intake + Entry Decision

## Goal

Turn scanner, Sheet, User, and other incoming observations into coherent, de-duplicated, time-relevant trade opportunities and govern the complete entry decision process in PAPER mode.

### TGT1 — Trade Intake, Source Identity, Outcome and Episode

Scope includes:

- source observations with `src_id`
- provenance preservation
- normalization of incoming intents
- Outcome / Opportunity identity
- time-relevant Episode concept
- datetime relevance
- de-duplication
- same-source/different-outcome handling
- different-source/same-outcome reconciliation
- existing-position awareness
- no repeated signal may silently increase position size
- ambiguous reconciliation may be delegated to the external Agents service

**Acceptance:** TM can distinguish duplicates, updates, new episodes, distinct outcomes, and existing-exposure rediscovery without creating duplicate operational trade paths.

### TGT2 — Entry Monitoring and Trade Intent

Scope includes:

- monitored candidate/opportunity behavior
- trigger detection
- confirmation handling
- retreat/wait
- invalidation
- current-market revalidation
- trade types: `DAY`, `BTST`, `STBT`, `POS`
- trade horizon
- F&O contract expiry as separate from horizon
- current F&O focus for equity/index
- future cash compatibility
- no automatic scale-in from repeated signals

**Acceptance:** An opportunity can progress from monitoring to an actionable proposed trade without broker execution.

### TGT3 — External Agents Validation Gate

Scope includes:

- Agents remains a separate service
- bounded decision packets
- mandatory verdict exactly one of:
  - `APPROVE`
  - `REJECT`
  - `RETREAT_WAIT`
- optional suggestion
- suggestions may propose modified or new trades
- suggestion returns to the owning TM domain and starts a new evaluation cycle if accepted for analysis
- Agents never send broker orders and do not own TM state
- Agent `REJECT` / `RETREAT_WAIT` escalates to User
- User responds `APPROVE` / `REJECT` / `RETREAT_WAIT`
- Agent failure does not become implicit approval

**Acceptance:** TM can obtain an independent view without surrendering ownership or authority to Agents.

### TGT4 — Risk Management Entry Gate

Scope includes:

- RM as highest runtime authority
- pre-trade risk evaluation
- account/portfolio visibility
- `UNMANAGED` positions counted for risk but never operated upon
- deterministic `PASS / BLOCK`
- every material RM block/intervention logged
- Setup/Admin-only risk configuration changes
- deliberate confirmation and audit trail for RM configuration changes
- no ordinary force/ignore-risk path
- final RM permission required before any risk-creating execution request could ever reach Module M

**TM2 Exit Criterion**

> In PAPER mode, TM can intake, reconcile, monitor, validate, obtain independent Agent review, escalate disagreements to the User, and apply Risk Management to decide whether a trade is permitted to proceed.

---

# TM3 — Position Management + Exit

## Goal

Manage the full lifecycle of broker-confirmed exposure, including adopted trades, deterministic management rules, strategic exit review, and closure — still safely exercised before live autonomous execution.

### TGT1 — Position Manager and Adoption

Scope includes:

- unified Position domain
- `MANAGED` / `UNMANAGED`
- explicit adoption of broker-originated positions
- adoption boundary remains hard until crossed
- sufficient information required according to management level
- native and adopted positions converge on the same management engine after adoption
- provenance remains available for audit

**Acceptance:** An external broker position can remain read-only or be explicitly adopted and then managed under the same machinery as a TM-native position.

### TGT2 — Deterministic Management Rules

Scope includes:

- SL
- TP
- TSL
- profit targets
- profit locks
- spot-based conditions
- premium-based conditions
- P&L conditions
- time exits
- trade horizon handling
- underlying invalidation
- policy-based management
- safe rule activation and audit logging

**Acceptance:** TM can deterministically monitor and manage open PAPER positions using explicit policies/rules.

### TGT3 — Exit Monitor and Position Evolution

Scope includes:

- protective exits
- deterministic policy exits
- strategic/discretionary exit proposals
- partial exit architecture
- duplicate/conflicting exit suppression
- DAY end-of-day protection
- deliberate `DAY → BTST/STBT/POS` or other valid conversion workflow
- horizon review
- position remains governed by broker truth

**Acceptance:** TM can move a PAPER position coherently from open exposure toward partial/full exit without duplicate actions.

### TGT4 — Exit Agents and Escalation

Scope includes:

- Exit Monitor may request independent Agents review for strategic/ambiguous exit decisions
- mandatory Agent verdict:
  - `APPROVE`
  - `REJECT`
  - `RETREAT_WAIT`
- optional suggestion
- Agent disagreement escalates to User
- hard RM exits bypass Agent veto/user approval in the normal trade flow
- suggestions may become new deterministic management proposals only through the owning TM domain

**TM3 Exit Criterion**

> In PAPER mode, TM can manage a broker-confirmed or adopted position from opening through management, strategic review, partial/full exit, and broker-confirmed closure.

---

# TM4 — Execution + Production Readiness

## Goal

Connect the already-proven TradeMonitor decision and management system to real broker execution through Module M, progressing from simulation to SEMI_AUTO and only later to AUTO.

### TGT1 — Module M and Broker Deployment

Scope includes:

- immutable/controlled ExecutionRequest concept
- entry and exit both use Module M
- Module M performs deployment only
- broker instrument resolution
- order construction
- submission
- idempotency / duplicate prevention
- acknowledgement tracking
- cancellation/replacement rules where justified
- partial fills
- rejection
- uncertain execution state
- reconciliation back to broker truth

**Acceptance:** The same authorized execution intent cannot accidentally become duplicate broker exposure because of retry/restart behavior.

### TGT2 — Execution Simulation, Replay, and Failure Injection

Scope includes:

- mock broker / broker simulator
- crash after submit but before acknowledgement
- restart with pending order
- partial fill
- reject
- disconnect
- stale market data
- broker reconciliation delay
- concurrent exit triggers
- replay of end-to-end trading sessions
- verify that no risk-creating request reaches M without current RM permission

**Acceptance:** Critical execution/recovery scenarios are reproducible and pass consistently before enabling real broker writes.

### TGT3 — SEMI_AUTO Controlled Forward Test

Scope includes:

- real broker execution
- explicit operator confirmations at configured discretionary points
- RM remains automatic and above User
- Agent disagreements escalate to User
- very small controlled exposure
- detailed audit review after each session/trade
- no leap to AUTO based merely on code completeness

**Acceptance:** Real execution behavior matches TM decisions and broker truth reliably under controlled conditions.

### TGT4 — AUTO Readiness

AUTO is a readiness gate, not an automatic entitlement after TGT3.

Requirements include:

- sufficient SEMI_AUTO evidence
- no unresolved reconciliation defects
- no duplicate execution defects
- reliable restart/recovery
- RM proven operationally
- Position/Exit behavior validated
- Agent degradation behavior validated
- clear operating safeguards
- explicit decision to enable AUTO

**TM4 Exit Criterion**

> TradeMonitor is production-ready for the level of autonomy that has been empirically validated. AUTO is enabled only when evidence justifies it.

---

## 3. Milestone Progression Rule

A later milestone may be prototyped experimentally, but it must not bypass the safety dependency of an earlier milestone.

The governing progression is:

`TM1 Reality → TM2 Entry Decision → TM3 Position Management → TM4 Real Execution`

The roadmap is intentionally asymmetric: **understanding and managing reality comes before creating live risk**.

---

## 4. Preservation and Change Control

This roadmap is a reference artifact and should live in the repository `docs/` folder.

Recommended files:

- `docs/TRADEMONITOR_THESIS.md`
- `docs/TRADEMONITOR_ROADMAP.md`
- optionally polished Word copies for human reading

Changes to the roadmap should be deliberate. If implementation reveals a genuine architectural need, update the roadmap and record why. Do not silently redefine completed milestone meaning.

Each accepted target should ideally be committed/tagged or otherwise checkpointed so the project always has a known-good return point.

---

## 5. Reference Summary

The roadmap can be remembered in four lines:

**TM1 — KNOW REALITY**  
Build the core, contexts, broker reconciliation, health, persistence, and PAPER runtime.

**TM2 — DECIDE ENTRY**  
Intake opportunities, handle time relevance/de-duplication, validate entries, consult Agents, enforce RM.

**TM3 — MANAGE POSITION**  
Adopt/manage positions, apply rules, monitor exits, use independent exit review where appropriate.

**TM4 — EXECUTE FOR REAL**  
Deploy through Module M, prove recovery/idempotency, progress PAPER → SEMI_AUTO → AUTO only with evidence.

---

> **Nothing creating risk reaches Module M without current Risk Management permission.**

This roadmap should always be read together with the TradeMonitor TM0 Architecture Thesis.
