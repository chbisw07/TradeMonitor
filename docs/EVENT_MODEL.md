# Event Model — TM1 Foundation

TM1 uses a durable event boundary for meaningful runtime activity.

## Principles

- Events are immutable records of meaningful runtime activity.
- The Core TM Manager records an event durably before publishing it to runtime subscribers.
- Events carry an ID, event name, timestamp, source, and structured payload.
- Runtime event handling remains synchronous in TM1 by design. This keeps the core deterministic while preserving a clean boundary for future concurrency.
- High-frequency market/P&L refreshes should not be confused with lifecycle transitions.

## Current Durable Events

Foundation events:

- `CORE_STARTED`
- `CORE_STOPPED`
- `CONTEXT_UPDATED`

Broker/position reconciliation events introduced in TGT2:

- `BROKER_RECONCILED`
- `BROKER_POSITION_DISCOVERED`
- `BROKER_POSITION_CHANGED`
- `BROKER_POSITION_CLOSED`
- `BROKER_POSITION_REOPENED`

Later milestones add intake, risk, management, execution, and recovery events without changing the core event contract unnecessarily.

## TM1/TGT4 Replay Semantics

`event_id` is the durable idempotency key for a domain event. Re-submitting the same event ID is a no-op for persistence and runtime publication.

Broker snapshots are not keyed by event ID; their `observed_at` timestamp is compared with the last accepted observation for that broker. Older observations are `STALE`; equal-timestamp observations are treated as `REPLAY`. Both remain auditable but cannot mutate canonical broker/position state.
