# Safety Invariants

- No live order placement exists in TM0.
- Broker reality is authoritative for order/position existence.
- Hard risk controls must not be bypassed by an LLM.
- Explicit user commands outrank advisory intelligence.
- Experimental code must not silently change trading semantics.
- AUTO mode must not be enabled until PAPER and SEMI_AUTO milestones are validated.
- All future consequential state changes should be auditable/timestamped.
