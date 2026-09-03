# Architecture

The canonical architecture is defined by the **TradeMonitor TM0 Architecture Thesis** and the **TradeMonitor Development Roadmap** in this `docs/` folder.

## TM1/TGT1 Runtime Shape

TradeMonitor uses a small **Core TM Manager** as a coordinator rather than a master trading algorithm. The Core Manager synchronizes runtime contexts, routes events, supervises lifecycle coordination, persists state, and exposes a coherent operating picture.

Canonical runtime contexts introduced in TGT1:

- Broker
- Market
- Trade
- Position
- Risk
- Decision
- Health

Domain modules own the meaning of their data. The Core Manager owns controlled synchronization and durable coordination.

## Event Boundary

Runtime changes are represented by structured, auditable events. TGT1 uses a synchronous event bus so the architecture has an explicit communication boundary without prematurely committing to threads or processes.

## Persistence and Recovery

TGT1 persists runtime contexts and events in SQLite. On restart, the Core Manager restores the latest durable context. Broker-truth reconciliation is implemented in TM1/TGT2; TGT1 establishes the persistence/recovery foundation it will use.

## Safety Boundary

TM1/TGT1 has **NO LIVE TRADING CAPABILITY**. No code in this target submits, modifies, or cancels broker orders.
