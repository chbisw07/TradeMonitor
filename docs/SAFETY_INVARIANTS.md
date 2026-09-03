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
