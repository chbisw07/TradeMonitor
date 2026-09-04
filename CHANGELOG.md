# Changelog

## Version 0.3.4 — Source-Independence Architecture Hardening

- Audited TM3/TGT4 for accidental Google Sheet/scanner schema coupling; core Intake/Entry/Risk/Position/Exit domains remain source-neutral.
- Added the canonical `CanonicalTradeObservation` adapter handoff type.
- Added generic `MappingTradeAdapter` for arbitrary external field-name mappings.
- Added `INTEGRATION_INTERFACE.md`, `SETUP_AND_ADAPTERS.md`, and `TM_SOURCE_INDEPENDENCE_AUDIT.md`.
- Reframed Google Sheets explicitly as an optional external adapter, never a core dependency.
- Added tests proving canonical and arbitrary external payloads normalize through the same TM intake contract.
- Preserved TM3/TGT4 behavior, PAPER-only operation, and zero broker-write capability.

## Version 0.3.3 / TM3-TGT4 — Exit Agents and Escalation

- Added external Agents review packets/results and durable audit history for strategic exit proposals.
- Added mandatory `APPROVE / REJECT / RETREAT_WAIT` exit verdict handling.
- Added User escalation for Agent disagreement, unavailability, or protocol failure.
- Added optional Agent suggestions as non-authoritative advice only.
- Added automatic approval/bypass for deterministic and protective exit paths.
- Added promotion of an existing strategic full-exit path when a higher-authority protective/deterministic trigger arrives.
- Added restart-safe exit review and Attention persistence.
- Preserved PAPER-only operation and zero broker-write / Module M capability.
- Full suite: 101 tests passing.

## Version 0.3.2 / TM3-TGT3 — Exit Monitor and Position Evolution

- Added durable Exit Monitor and Exit Proposal decision model.
- Added protective, deterministic, and strategic exit classifications.
- Added `EXIT_ALL`, `EXIT_QTY`, and `EXIT_PERCENT` proposal shapes.
- Added duplicate/coalesced full-exit handling and conflicting partial-exit suppression.
- Routed triggered deterministic management rules into Exit Monitor proposals.
- Added DAY end-of-day protection and explicit holding-intent conversion.
- Added broker-truth convergence that marks pending proposals satisfied when exposure is closed.
- Added restart persistence and control-room exit-proposal counts.
- Preserved PAPER-only, `UNMANAGED` read-only, and no-Module-M boundaries.
- Validation: 91 tests passed.

## Version 0.3.1 / TM3-TGT2 — Deterministic Management Rules

- Added durable deterministic managed-position rule engine.
- Added SL, TP, TSL, profit-lock, spot/premium/P&L, time/horizon, and underlying-invalidation rule families.
- Added named management-policy installation and explicit rule cancellation.
- Added stateful long/short trailing logic and durable profit-lock activation.
- Added restart persistence for rule runtime state.
- Added control-room management-rule counts.
- Preserved PAPER-only, `UNMANAGED` read-only, and no-ExecutionRequest boundaries.
- Validation: 84 tests passed.

- Added durable deterministic managed-position rule engine.
- Added SL, TP, TSL, profit-lock, spot/premium/P&L, time/horizon, and underlying-invalidation rule families.
- Added named management-policy installation and explicit rule cancellation.
- Added stateful long/short trailing logic and durable profit-lock activation.
- Added restart persistence for rule runtime state.
- Added control-room management-rule counts.
- Preserved PAPER-only, `UNMANAGED` read-only, and no-ExecutionRequest boundaries.
- Validation: 84 tests passed.

# Changelog

## Version 0.3.0 / TM3-TGT1 — Position Manager and Adoption

- Added explicit `UNMANAGED -> MANAGED` adoption workflow for broker-originated positions.
- Added durable Position Management Profiles carrying asset/instrument/trade type, horizon, F&O expiry, adoption authority and reason.
- Required current-runtime broker reconciliation before adoption.
- Preserved broker quantity/state/identity as factual truth during and after adoption.
- Added `BROKER_ADOPTED` provenance while keeping one canonical Position record.
- Added restart-safe management-profile persistence and post-adoption broker reconciliation tests.
- Preserved the hard UNMANAGED read-only boundary and zero broker-write capability.
- Full suite: 75 tests passing.

## Version 0.2.3 / TM2-TGT4 — Risk Management Entry Gate

- Added highest-authority deterministic pre-trade Risk gate (`PASS / BLOCK`).
- Added versioned Risk Profiles without inventing numeric bootstrap thresholds.
- Added account/portfolio risk visibility including `UNMANAGED` broker positions while preserving their hard read-only boundary.
- Added current-runtime broker-reconciliation requirement before fresh risk can be approved.
- Added durable Risk decision records, block audit events, and Attention surfacing.
- Added two-step Setup/Admin Risk profile change workflow with explicit reason, confirmation, versioning, and audit.
- Added explicit re-evaluation boundary for previously `RISK_BLOCKED` entries; profile changes never silently revive trades.
- Added `RISK_APPROVED` handoff state; no ExecutionRequest, Module M, or broker-write capability exists yet.
- Full suite: 70 tests passing.

## 0.2.2 — TM2/TGT3

- Added external Agents-service gateway contract for entry validation.
- Added durable Agent review packets/results and audit history.
- Added mandatory `APPROVE / REJECT / RETREAT_WAIT` verdict handling.
- Added User escalation for Agent disagreement or unavailability.
- Added `READY_FOR_RISK` as the post-validation handoff state; no RM or execution logic is implemented yet.
- Preserved optional Agent suggestions as non-authoritative advice.
- Added restart-safe review/attention persistence and tests.
- No broker-write/live-trading capability added.

## Version 0.2.1 / TM2-TGT2 — Entry Monitoring and Trade Intent

- Added durable Entry Intent monitoring tied to time-relevant Episodes.
- Added deterministic trigger, completed-candle confirmation, invalidation, and RETREAT_WAIT/rearm flow.
- Added final current-market premium-zone revalidation so stretched option entries retreat rather than chase.
- Added frozen holding intents `DAY`, `BTST`, `STBT`, and `POS`, with horizon separate from F&O expiry.
- Added initial `EQUITY` / `INDEX` asset scope and `CASH` / `FUTURE` / `OPTION` instrument model; CASH remains future-compatible.
- Added restart-safe entry-intent persistence and Core trade-context summaries.
- Preserved PAPER-only operation: READY_FOR_REVIEW is not execution permission, Agents/RM/Module M remain future gates.
- Full suite: 52 tests passing.


## Version 0.2.0 / TM2-TGT1 — Trade Intake, Source Identity, Outcome and Episode

- Added durable source observations with explicit `src_id` and provenance.
- Added normalized broad Outcome identity and time-relevant Episode identity.
- Added deterministic temporal/contract-context reconciliation and exact observation de-duplication.
- Added optional bounded ambiguity-resolution port for the separate external Agents service.
- Added existing-position awareness; rediscovery never creates scale-in permission.
- Added restart-safe intake persistence and Core trade-context summary integration.
- Added TM2/TGT1 acceptance tests while preserving PAPER-only/no-broker-write safety.


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
