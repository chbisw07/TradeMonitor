# Broker Interfaces — TM4/TGT1

TradeMonitor deliberately separates **broker truth** from **broker mutation**.

## `Broker` — factual/read-only interface

The original `Broker` contract remains the universal truth/reconciliation interface. It can return a coherent `BrokerAccountSnapshot` containing positions, funds/margins, and supported order/fill summaries. All brokers used by TM must be able to provide factual reality through this boundary.

## `ExecutionBroker` — explicit Module M capability

TM4 introduces a second, stronger contract that extends `Broker` only for adapters deliberately capable of execution. It exposes:

- instrument resolution;
- normalized order submission;
- broker-order lookup by broker order ID;
- broker-order lookup by TM client/idempotency ID;
- explicit cancellation.

TradeMonitor core domains never call these methods. Only Module M receives an authorized `ExecutionRequest` and talks to an `ExecutionBroker`.

## TGT1 Safety

TM4/TGT1 supplies only a deterministic simulation execution adapter. The Core rejects execution through adapters reporting `is_simulation = False`.

Real broker integration is therefore **not enabled** by TGT1. Real broker SEMI_AUTO work belongs to TM4/TGT3 after TGT2 execution replay/failure validation.

## Idempotency / uncertainty

The TM idempotency key is sent as the broker client-order identity. Module M durably records `SUBMITTING` before calling the broker. If acknowledgement is lost, the request becomes `UNCERTAIN` and reconciliation by client-order ID is attempted; TM does not infer failure and blind-submit another order.


## TM4/TGT3 Zerodha reference adapter

`ZerodhaExecutionBroker` is the first optional real implementation of `ExecutionBroker`. It uses the official Kite Connect Python client. Broker-specific order tags/statuses/position fields are normalized entirely inside the adapter. Core TM continues to use broker-neutral contracts.
