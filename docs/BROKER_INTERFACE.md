# Broker Interface — TM1/TGT2

TM1/TGT2 introduces the first broker abstraction as a **strictly read-only truth interface**.

## Current Contract

A broker adapter exposes its identity and returns one coherent `BrokerAccountSnapshot` containing supported read-side facts such as:

- broker positions;
- funds/margin summary;
- order count / fill count when available.

The snapshot is consumed by the Core/Position reconciliation flow. Broker-reported position quantity/state is factual truth.

## Explicitly Absent

The TGT2 `Broker` contract has no operation to:

- place/submit an order;
- modify/cancel an order;
- exit/hedge a position;
- adopt an external position;
- otherwise mutate broker state.

Live execution belongs to TM4 / Module M.

## Position Boundary

New broker positions discovered through reconciliation enter TM as `UNMANAGED`. They are visible and durable but read-only until a later explicit adoption workflow changes their management status.
