# Architecture

The canonical architecture is defined by the **TradeMonitor TM0 Architecture Thesis** and the **TradeMonitor Development Roadmap** in this `docs/` folder.

## Core Runtime

TradeMonitor uses a small **Core TM Manager** as a coordinator rather than a master trading algorithm. Domain modules own their specialist meaning; Core owns synchronization, durable coordination, event routing, and the coherent operating picture.

Canonical runtime contexts currently include Broker, Market, Trade, Position, Risk, Decision, and Health.

## TM1/TGT2 Broker Truth Boundary

Broker reality is factual truth for broker orders/fills/positions. TGT2 introduces a strictly read-only Broker adapter that supplies one coherent account snapshot to the Core/Position domain.

The Position domain reconciles persisted state to broker truth. Broker-reported quantity/state wins. A broker position omitted from a coherent current snapshot is considered closed by broker reality.

## Unified Positions

There is one Position universe with an orthogonal management status:

- `MANAGED` — TM has management authority (full behavior arrives in TM3).
- `UNMANAGED` — visible/reconciled but a hard read-only boundary until explicit adoption.

New positions discovered directly at the broker are always `UNMANAGED`. Origin/provenance is preserved separately from management status.

## Event/Persistence Boundary

Broker reconciliation produces structured position events and refreshes durable Broker/Position contexts. SQLite remains the TM1 persistence mechanism. The synchronous event bus remains an explicit communication boundary without prematurely choosing a threading/process architecture.

## Safety Boundary

TM1/TGT2 has **NO LIVE TRADING CAPABILITY**. The Broker contract in this target has no order submission, modification, cancellation, exit, hedge, or adoption method.

## TM1/TGT3 Health and Fault Containment

TradeMonitor uses a hybrid fault model consistent with the TM0 thesis.

**Vertical ownership:** a child/component reports failure to the nearest competent parent/domain owner first. That owner handles/retries/degrades locally when safe. Only unresolved faults propagate upward, carrying summarized domain meaning and impact.

**Horizontal ownership:** peer domains are responsible for containing their own failures and reporting health/impact to the Core TM Manager. A failing non-critical peer does not automatically collapse unrelated peers.

Core coordinates the coherent health picture; it is not a global raw-exception handler.

## TM1/TGT3 Control Room

The console is an operational control-room view, not a scrolling business-logic owner. It renders one coherent snapshot containing domain health, capability impact, unified Positions (`MANAGED` / `UNMANAGED`), and an Attention queue. Attention is durable across restart.

TM1/TGT3 remains PAPER-only and broker-read-only.

## TM1/TGT4 Recovery and Replay Boundary

TM1 recovery is state-convergent rather than action-replaying. Persisted contexts are restored, then newer external facts—especially broker truth—are reconciled. Older or already-accepted broker observations cannot roll state backward. Exact duplicate events are harmless through event-ID idempotency. Replay/audit activity may add log records, but must not manufacture new broker exposure or change the `MANAGED` / `UNMANAGED` boundary.

A stable business-state fingerprint is used by replay validation to distinguish semantic state from bookkeeping timestamps and context-version increments.


## TM2/TGT1 intake identity

Trade intake separates three questions: **Source Observation** (who/what said it and when), **Outcome** (the broad trading idea), and **Episode** (the currently relevant manifestation of that Outcome in market time/contract context). Candidate remains an operational/UI notion rather than another heavy domain entity. Clear reconciliation is deterministic. A genuinely ambiguous same-Outcome Episode question may be delegated through a bounded interface to the separate external Agents service; ownership returns to Intake. Existing broker-confirmed exposure is awareness only and repeated signals never imply scale-in.


## TM2/TGT2 entry monitoring

A time-relevant Episode may be admitted into the Entry domain as a durable Entry Intent. The Entry domain owns deterministic trigger, optional completed-candle confirmation, underlying invalidation, horizon/expiry boundaries, and current contract-premium revalidation. `RETREAT_WAIT` is a deliberate reversible state and requires rearm before another cycle. `READY_FOR_REVIEW` is only a handoff point for later validation; it is not execution permission. Entry monitoring does not call Module M and does not write to the broker.

## TM2/TGT3 External Agents Validation Boundary

The Agents capability is a **separate external service**. TradeMonitor owns only the gateway contract and the calling workflow. The Entry domain delegates a bounded validation task after deterministic entry monitoring reaches `READY_FOR_REVIEW`; control always returns to the Entry domain.

`APPROVE` advances to `READY_FOR_RISK`. `REJECT` and `RETREAT_WAIT` are lower-authority opinions and therefore escalate to the User. An optional Agent suggestion is advice only and must re-enter normal TM evaluation if pursued. Agent failure is never treated as approval.

Agents cannot mutate TM state directly, cannot call Module M, cannot access broker execution, and cannot bypass Risk Management.

## TM2/TGT4 Risk Management Entry Gate

Risk Management (RM) is the highest runtime operational authority inside TradeMonitor. The TM2/TGT4 entry gate evaluates a fully validated entry intent only after it reaches `READY_FOR_RISK`. A Risk decision is deterministic: `PASS` or `BLOCK`.

RM evaluates the proposed new exposure against the active versioned Risk Profile and current broker-confirmed account state. All open broker positions contribute to portfolio visibility, including `UNMANAGED` positions. Their exposure can therefore cause a new TM entry to be blocked, but the hard `UNMANAGED` boundary remains intact: RM may observe/count them but cannot modify, exit, hedge, or otherwise operate on them.

The bootstrap profile intentionally invents no numeric trading limits. Numeric limits are introduced only through the explicit Setup/Admin profile-change workflow. Broker truth, however, must be reconciled in the current runtime before RM can approve creation of new exposure. Persisted last-known broker facts alone are insufficient.

A profile change is two-step: propose with a reason, then explicitly confirm. Confirmation creates a new immutable profile version and is audited. There is no ordinary `force`, `ignore-risk`, or trade-level risk override path. A profile change does not automatically revive a previously `RISK_BLOCKED` trade; explicit re-evaluation is required.

A Risk `PASS` moves the entry to `RISK_APPROVED`. This is still not an `ExecutionRequest`. Module M remains outside TM2 and no broker-write path exists.


## TM3/TGT1 — Position adoption boundary

TradeMonitor maintains one canonical Position universe. `MANAGED` / `UNMANAGED` is a management-authority attribute, not a different position type. Broker-discovered positions begin `UNMANAGED` and remain read-only to TM management until an explicit adoption workflow succeeds.

Adoption requires current-runtime broker reconciliation and a durable Position Management Profile (asset class, instrument type, trade type, horizon, F&O expiry where applicable, adopting authority and reason). Adoption changes only TM management authority/provenance; broker quantity, average price, identity and open/closed state remain broker truth. Adopted and future TM-native positions use the same management-profile shape so downstream Position Management can remain origin-agnostic.


## TM3/TGT2 — Deterministic Position-Management Rules

A specialist `ManagementRuleEngine` lives inside the Position domain. It owns validation, persistence, stateful evaluation, and lifecycle events for explicit management rules. The engine can emit an `EXIT_REVIEW` management signal, but it is intentionally not an Exit Monitor and cannot create broker-facing execution.

The flow is:

`MANAGED Position + Management Profile + Current Facts -> ManagementRuleEngine -> Rule Evaluations / EXIT_REVIEW signals -> (TM3/TGT3 Exit Monitor later)`

The rule engine is below the Position ownership boundary, remains deterministic, and never crosses the `UNMANAGED` boundary.


## TM3/TGT3 — Exit Monitor and Position Evolution

The Exit Monitor is the Position/Exit domain owner for proposed position reduction. It consumes deterministic management-rule signals and explicit strategic/user requests and creates durable `ExitProposal` decision objects. Exit proposals are not broker orders and cannot reach a broker in TM3.

- Protective, deterministic, and strategic exit proposals are distinguished.
- `EXIT_ALL`, `EXIT_QTY`, and `EXIT_PERCENT` are represented without execution.
- A pending full-exit proposal owns the position's exit path; later full-exit triggers are coalesced and competing partial exits are suppressed.
- DAY positions can produce an end-of-day exit proposal unless deliberately converted beforehand.
- Holding-intent conversion updates the Position Management Profile only; it is not a broker operation.
- Broker truth remains final: if reconciliation shows the position closed, pending exit proposals are marked satisfied by broker reality.
- `UNMANAGED` positions remain outside Exit Monitor authority.
