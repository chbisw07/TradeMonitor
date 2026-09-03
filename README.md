# TradeMonitor

TradeMonitor is intended to become a professional real-time trade monitoring and execution system for Indian markets. Future versions may monitor candidate stocks, entry conditions, broker positions, operational instructions, Google Sheet and CGPT inputs, and eventually support broker execution and position management.

## Current Status

TM0 is architecture and repository setup only.

**NO LIVE TRADING CAPABILITY EXISTS IN TM0.**

This repository currently contains no trading logic, broker execution, scanner logic, LLM logic, market-data polling, Google Sheets integration, order placement, or state-machine behavior.

## Future Components

- Candidate management
- Domain model and state machine
- Market-data provider interfaces
- Risk and execution engines
- Broker abstraction and reconciliation
- Position management
- Event persistence and replay
- Console UI for V1
- Optional web UI later
- Google Sheet and CGPT ingestion
- Advisory intelligence

## Development Setup

Create a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Install in editable mode with development dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Run the development application:

```bash
python scripts/run_dev.py
```
