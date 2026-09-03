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
