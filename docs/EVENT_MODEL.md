# Event Model — TM1/TGT1 Foundation

TM1/TGT1 introduces the first durable event boundary.

## Principles

- Events are immutable records of meaningful runtime activity.
- The Core TM Manager records an event durably before publishing it to runtime subscribers.
- Events carry an ID, event name, timestamp, source, and structured payload.
- Runtime event handling is synchronous in TGT1 by design. This keeps the core deterministic while preserving a clean boundary for future concurrency.
- Domain-specific event taxonomies are intentionally deferred to later targets.

## Current Durable Events

TGT1 records foundational runtime events such as:

- `CORE_STARTED`
- `CORE_STOPPED`
- `CONTEXT_UPDATED`

Later milestones will add broker, intake, risk, position, execution, and recovery events without changing the core event contract unnecessarily.
