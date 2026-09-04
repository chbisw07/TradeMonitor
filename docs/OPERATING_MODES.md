# Operating Modes

## Execution Modes

- PAPER
- SEMI_AUTO
- AUTO

## System States

- RUNNING
- PAUSED
- SAFE
- EMERGENCY

Detailed semantics are specification-controlled and will be defined in TM0/TM1 before implementation.


## TM4/TGT3 semantics

`PAPER` is the default. `SEMI_AUTO` enables a controlled live path only when real broker writes are explicitly armed. Each real request still requires a durable User APPROVE decision within its TTL and all normal RM/broker-truth checks. `AUTO` is intentionally refused in TGT3.
