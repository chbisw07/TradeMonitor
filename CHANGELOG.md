# Changelog

## Version 0.1.3 / TM1-TGT4 — PAPER Runtime, Recovery and Replay Validation

- Added stale/replayed broker snapshot classification and rejection of out-of-order truth.
- Added idempotent duplicate-event persistence/publication by event ID.
- Added stable runtime business-state fingerprints for replay validation.
- Added ungraceful restart and offline broker-change recovery validation.
- Added broker degraded→healthy recovery with Attention resolution.
- Added Attention de-duplication for repeated identical outages.
- Added generic stale-context degradation without cross-domain collapse.
- Added replay/recovery acceptance suite; complete test suite is 30/30 passing.
- Preserved PAPER-only runtime and zero broker write capability.

## Version 0.1.2 / TM1-TGT3 — Health, Fault Containment and Control Room

- Added domain health reporting with capability-specific impact.
- Added vertical nearest-owner fault containment/escalation semantics.
- Added horizontal peer-domain degradation without global collapse.
- Added durable operator Attention queue.
- Added unified control-room rendering for health, positions, and attention.
- Added broker degraded-mode behavior and operator visibility.
- Preserved PAPER-only runtime and zero broker write capability.

## Version 0.1.1 / TM1-TGT2 — Broker Truth and Position Reconciliation

- Added read-only broker account snapshot contract and deterministic MockBroker.
- Added durable canonical Position records and broker truth reconciliation.
- Added `MANAGED` / `UNMANAGED` management status and hard unmanaged read-only guard.
- Added broker/position runtime summaries and reconciliation audit events.
- Added restart/closure reconciliation and TGT2 acceptance tests.
- Preserved zero broker write/live trading capability.


## Version 0.1.0 / TM1-TGT1

- Added Core TM Manager coordination foundation
- Added broker/market/trade/position/risk/decision/health runtime contexts
- Added explicit synchronous event bus
- Added immutable structured domain events
- Added SQLite runtime context and audit-event persistence
- Added restart/context restoration foundation
- Added concise PAPER-only console status view
- Added unit and integration tests for context, event, persistence, restart, and console behavior
- Updated architecture/milestone documentation to reference the canonical TM0 thesis and four-milestone roadmap
- Still no live trading capability

## Version 0.0.1 / TM0

- Initial project skeleton
- No trading/execution logic
