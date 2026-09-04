# Zerodha Read-Only Integration / Reconciliation Stage

This stage is the operational bridge between the 159-test TM4/TGT3 baseline and any future live forward test.

## Safety boundary

Use `ZerodhaReadOnlyBroker` for the first real-account connection. It implements only TM's read-only `Broker` contract and intentionally does **not** implement `ExecutionBroker`.

Allowed broker calls:

- positions
- equity margins/funds
- orders (count/observation only)
- trades/fills (count/observation only)

Unavailable through this adapter:

- place order
- modify order
- cancel order
- any BUY/SELL deployment

`TM_ALLOW_REAL_BROKER_WRITES` is forcibly set to `false` by the read-only verification script.

## Setup

Install optional Zerodha support:

```bash
pip install -e '.[zerodha]'
```

Create `.env` locally (never commit credentials):

```env
TM_EXECUTION_MODE=PAPER
TM_ALLOW_REAL_BROKER_WRITES=false
ZERODHA_API_KEY=your_api_key
ZERODHA_ACCESS_TOKEN=your_current_daily_access_token
```

## Step 1 — broker-only read check

```bash
python scripts/zerodha_read_only.py --no-persist
```

Verify funds and open positions against Kite. This command does not write into TradeMonitor's database.

## Step 2 — TradeMonitor reconciliation

```bash
python scripts/zerodha_read_only.py
```

Expected behavior:

- Zerodha open net positions become canonical TM positions.
- A position not previously owned/adopted by TM is `UNMANAGED` with origin `BROKER_EXTERNAL`.
- TM observes but cannot manage an `UNMANAGED` position.
- broker context reports `read_only=true` and `runtime_reconciled=true`.
- closed Zerodha intraday rows with net quantity zero are not treated as current exposure; absence closes a previously open canonical position on reconciliation.

## Acceptance gate before SEMI_AUTO writes

Do not move to controlled live deployment until all of the following are manually checked:

1. Zerodha available funds approximately match Kite.
2. Every current open position has the correct exchange, symbol, product, quantity and average price.
3. External positions appear as `UNMANAGED`.
4. No unexpected TM position appears as `MANAGED`.
5. A second reconciliation is stable/idempotent.
6. Broker writes remain disabled.
