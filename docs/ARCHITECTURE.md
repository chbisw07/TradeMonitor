# Architecture

TradeMonitor is designed so core and business logic remain independent of any user interface. V1 will use an interactive console UI. A web UI may be added later without redesigning the core.

## External Inputs

- Scanner
- Google Sheet
- CGPT analysis
- User commands
- Market data
- Broker

## TradeMonitor Core

- Candidate Manager
- State Machine
- Trigger/Confirmation Engine
- Risk Engine
- Execution Engine
- Position Manager
- Exit Engine
- Event Store
- Broker Reconciliation

## Interfaces

- Console UI now
- Optional Web UI later
