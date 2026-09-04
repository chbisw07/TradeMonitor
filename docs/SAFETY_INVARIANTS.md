# Safety Invariants

- Broker reality is factual truth for broker order/position existence and quantity.
- Nothing creating risk may eventually reach Module M without current Risk Management permission.
- Risk Management cannot be bypassed by an ordinary User command or by advisory intelligence.
- `UNMANAGED` positions are read-only to TradeMonitor until explicitly adopted.
- Broker discovery never implies adoption.
- Repeated/rediscovered exposure must never silently increase position size.
- A missing broker acknowledgement must never be treated as proof that an order failed (execution work is deferred to TM4).
- Experimental code must not silently change trading semantics.
- AUTO mode must not be enabled until PAPER and SEMI_AUTO evidence justifies it.
- Consequential state changes and Risk Management blocks/interventions must be auditable/timestamped.
- TM1/TGT2 contains no broker write operations.
- A failed subsystem must never silently increase TM capability or authority.
- A non-critical horizontal domain failure must not unnecessarily collapse unrelated domains.
- Vertical failures are handled by the nearest competent owner before escalation.
- Broker truth becoming unavailable must be surfaced; stale/unknown broker state must not be treated as current truth.
- TM1/TGT3 remains PAPER-only with no broker write operations.

## TM1/TGT4 Recovery / Replay Invariants

- Older broker truth must never overwrite newer accepted broker truth.
- Replayed external facts must not create duplicate business side effects.
- Exact duplicate domain events are processed at most once by event ID.
- Restart must restore durable state before normal coordination resumes.
- Failure/recovery must not change `UNMANAGED` into `MANAGED`.
- Repeated identical failures should not create unbounded duplicate operator Attention.
- Recovery may restore capability; failure may never silently increase authority.
- TM1 remains PAPER-only and exposes no broker-write API.


## TM2/TGT1 Intake Invariants

- Source provenance is never discarded merely because observations reconcile to the same Outcome/Episode.
- Outcome identity and time-relevant Episode identity remain separate.
- Older/stale source observations may be retained for provenance but must not replace the currently relevant Episode.
- Exact source observation replay must be idempotent.
- Repeated/rediscovered signals never constitute add/scale-in permission.
- Existing `MANAGED` or `UNMANAGED` broker exposure may influence intake awareness, but Intake has no authority to operate on that exposure.
- Ambiguity delegation is through an explicit external-service port; TM core contains no Agents implementation.
- TM2/TGT1 remains PAPER-only and exposes no broker-write path.


## TM2/TGT2 Entry Monitoring Invariants

- `READY_FOR_REVIEW` is not execution permission.
- Nothing in Entry Monitoring can write to the broker or create an `ExecutionRequest`.
- F&O trade horizon must not extend beyond contract expiry.
- Failed confirmation or unacceptable current premium may retreat/wait rather than chase.
- A `RETREAT_WAIT` intent does not silently rearm itself.
- Repeated/re-discovered opportunity input does not imply scale-in.
- Nothing creating risk reaches Module M without current Risk Management permission.

## TM2/TGT3 Agent-Gate Invariants

- Agents are lower authority than the User and Risk Management.
- Agent `APPROVE` is not execution permission; it only permits progression to the Risk gate.
- Agent `REJECT` / `RETREAT_WAIT` requires User resolution for the submitted entry.
- Agent unavailability, malformed response, or correlation failure must never become implicit approval.
- Agent suggestions are non-authoritative and cannot directly create or modify broker exposure.
- No path from Agents reaches Module M directly.

## TM2/TGT4 Risk Gate Invariants

- Risk Management is the highest runtime operational authority inside TM.
- A new-exposure proposal may be Risk-approved only after broker truth has been reconciled in the current runtime.
- Last-known persisted broker state is not sufficient to authorize fresh risk after restart.
- Every `BLOCK` is durably logged with profile version, reason(s), proposal facts, and portfolio metrics.
- `UNMANAGED` broker positions count toward portfolio/open-position/exposure risk but remain a hard read-only boundary.
- Risk settings may change only through the explicit Setup/Admin propose + confirm workflow.
- No ordinary trade command can force or ignore a Risk block.
- Risk profile changes are versioned and audited; they do not silently resurrect blocked trades.
- A `RISK_BLOCKED` entry requires an explicit re-evaluation request before another Risk gate can occur.
- `RISK_APPROVED` is permission from RM only; it is not an ExecutionRequest and does not invoke Module M.


## TM3/TGT1 adoption invariants

- `UNMANAGED` is a hard read-only boundary until explicit adoption.
- Adoption never performs a broker write and never changes broker truth.
- Current-runtime broker reconciliation is required before adoption.
- Closed positions cannot be adopted and already-managed positions are not re-adopted.
- F&O adoption requires expiry and an explicit holding intent/horizon.
- Every successful adoption is auditable and survives restart.
- Broker reconciliation after adoption may change quantity/state/average price but must preserve valid TM management authority/profile until broker truth closes the position.


## TM3/TGT2 deterministic-management invariants

- Deterministic management rules may be attached only to open `MANAGED` positions with a valid management profile.
- `UNMANAGED` positions remain read-only; no rule may be installed or evaluated as management authority across that boundary.
- Rule triggers are management signals, not broker actions. They create no `ExecutionRequest` and never invoke Module M.
- Stateful rules such as trailing SL and profit lock must persist their armed/watermark state across restart.
- Rule creation, policy installation, arming/ratcheting, triggering, and cancellation are auditable.
- Broker truth remains authoritative for position quantity/state/average price while TM rules govern only management intent.
- TM3/TGT2 remains PAPER-only and exposes no broker-write path.


## TM3/TGT3 Exit Safety Invariants

- Exit proposals are decision objects only; TM3/TGT3 has no broker-write path and no `ExecutionRequest`.
- `UNMANAGED` positions cannot receive exit proposals or holding-intent conversion.
- Multiple full-exit triggers for the same position are coalesced into one pending full-exit path.
- A pending full exit suppresses later partial-exit proposals; a later full exit supersedes earlier pending partial proposals.
- DAY end-of-day handling cannot silently convert a DAY position into overnight exposure.
- Position conversion is explicit, user-attributed, reasoned, logged, and changes TM intent only.
- Broker-confirmed closure overrides internal exit expectations and satisfies pending proposals.


## TM3/TGT4 Exit-review invariants

- Agents are advisory and external; they never own or execute an exit.
- `REJECT` / `RETREAT_WAIT` from Agents cannot silently cancel an otherwise valid TM decision; they escalate to the User.
- Agent failure never implies `APPROVE`.
- Protective/deterministic exits never wait for Agent approval.
- A protective/deterministic trigger must not remain blocked behind a strategic Agent/User review.
- Agent suggestions are logged advice only until the owning TM domain deliberately turns them into a new proposal/rule cycle.
- TM3/TGT4 creates no broker write and no ExecutionRequest.

## Source-independence invariants

- TradeMonitor core domains must not depend on source-specific worksheet names, column names, payload keys, or proprietary formats.
- Every external trade source must cross an adapter boundary into the canonical Intake contract.
- Adding or removing a Google Sheet/scanner/web adapter must not alter core authority, Risk, Entry, Position/Exit, or execution semantics.
- Direct/manual input must enter through the same Intake boundary and may not bypass de-duplication, Agents, Risk Management, or later Module M controls.
- Source repetition or source count never grants execution authority and never implies scale-in.

## TM4/TGT1 Execution / Module M Invariants

- Nothing creating risk reaches Module M without current Risk Management permission.
- An ENTRY `ExecutionRequest` must bind to the latest matching RM `PASS`, current Risk-profile version, and unchanged broker truth used by that Risk decision.
- Module M performs deployment mechanics only; it never judges trade quality or grants Risk permission.
- ENTRY and EXIT use the same Module M deployment contract.
- `UNMANAGED` positions can never generate an exit `ExecutionRequest`.
- Idempotency is durable before broker submission; repeated/restarted deployment of the same request must reconcile rather than blindly resubmit.
- Missing/failed acknowledgement means `UNCERTAIN`, never assumed rejection/failure.
- Broker order truth controls acknowledgement, partial-fill, fill, rejection, and cancellation state.
- The read-only `Broker` contract remains distinct from the opt-in write-capable `ExecutionBroker` contract.
- TM4/TGT1 permits simulation execution adapters only; real broker writes remain disabled.

## TM4/TGT2 Failure / Replay Invariants

- Broker acceptance with lost acknowledgement becomes `UNCERTAIN`; TM reconciles by idempotency/client-order identity and never blind-resubmits.
- Reconciliation transport failure is contained as `UNCERTAIN` and does not erase durable execution intent.
- Explicitly stale/unavailable Market context blocks creation/deployment of new exposure.
- Broker-order observations older than the last accepted broker observation cannot roll execution state backward.
- Concurrent repeated deployment of one ExecutionRequest must result in at most one broker submission.
- Concurrent full-exit triggers must converge on one active full-exit path before Module M.
- Real broker writes remain disabled throughout TM4/TGT2.

## TM4/TGT3 SEMI_AUTO Invariants

- PAPER remains the default execution mode.
- Real broker writes require SEMI_AUTO mode and an explicit global arming flag; AUTO is unavailable.
- Every real ExecutionRequest requires an explicit current User approval bound to that request's idempotency key.
- User approval expires; expiry requires a fresh decision.
- User approval never overrides Risk Management.
- Re-reading unchanged broker account facts may refresh broker truth without invalidating Risk merely because the local observation timestamp changed. Material broker Risk state changes invalidate prior Risk permission.
- Real-broker adapters are optional plugins behind the same ExecutionBroker contract; no broker-specific schema may leak into core domains.
