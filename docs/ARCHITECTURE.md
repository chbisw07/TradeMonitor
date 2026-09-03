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
