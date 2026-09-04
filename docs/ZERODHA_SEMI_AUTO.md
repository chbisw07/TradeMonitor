# Zerodha SEMI_AUTO Setup — TM4/TGT3

Zerodha is the first reference real-broker adapter. The core remains broker-neutral; another broker can implement the same `ExecutionBroker` interface.

## Install

```bash
pip install -e '.[zerodha]'
```

The current official package line used by TM is Kite Connect Python `5.2.x`.

## Environment

Keep real credentials only in local `.env`:

```env
TM_EXECUTION_MODE=SEMI_AUTO
TM_ALLOW_REAL_BROKER_WRITES=false
TM_SEMI_AUTO_APPROVAL_TTL_SECONDS=60

ZERODHA_API_KEY=...
ZERODHA_ACCESS_TOKEN=...
```

Start with `TM_ALLOW_REAL_BROKER_WRITES=false`. The access token is a daily Kite session token and must be refreshed through Zerodha's normal login/session flow.

## Read-only check first

With credentials configured, the Zerodha adapter can reconcile positions/funds without writing orders. Keep real writes disabled while validating broker truth.

## Controlled execution sequence

Only after an already-authorized `ExecutionRequest` exists:

```bash
python scripts/zerodha_semi_auto.py --list
python scripts/zerodha_semi_auto.py --request-approval ER-... --reason 'controlled 1-lot forward test'
python scripts/zerodha_semi_auto.py --approve ER-... --confirm APPROVE --reason 'reviewed order details'
```

Before deployment, deliberately change:

```env
TM_ALLOW_REAL_BROKER_WRITES=true
```

Then, within the approval TTL:

```bash
python scripts/zerodha_semi_auto.py --deploy ER-... --confirm-deploy 'DEPLOY ER-...'
```

Reconcile broker order truth:

```bash
python scripts/zerodha_semi_auto.py --reconcile-order ER-...
```

If cancellation is required:

```bash
python scripts/zerodha_semi_auto.py --cancel ER-... --confirm-cancel 'CANCEL ER-...'
```

## Forward-test discipline

The first live test should use the smallest practical exposure and a liquid instrument during normal market conditions. Verify the symbol, side, quantity, product, order type, price, RM PASS, and current broker state before approving. Review TM logs and broker orderbook after the test before attempting another live request.
